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
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import atomic_write, lock, mark_clone, safe_bytes, scrub, verify_clone

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
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {scrub(msg)}"
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
    if "repo" not in cfg: cfg["repo"] = origin_url() or DEFAULT_REPO
    cfg.setdefault("branch", "main")
    cfg.setdefault("install_dir", str(DEFAULT_INSTALL_DIR))
    cfg.setdefault("clone_dir", str(DEFAULT_CLONE_DIR))
    cfg.setdefault("python", sys.executable)
    cfg.setdefault("interval_min", 10)
    cfg.setdefault("no_vectors", False)
    validate_config(cfg)
    return cfg


def validate_config(cfg):
    for key in ("repo", "branch", "install_dir", "clone_dir", "python", "source"):
        if not isinstance(cfg.get(key), str) or not cfg[key].strip(): raise ValueError("invalid updater configuration")
    if cfg["source"] not in {"git", "release"} or not isinstance(cfg.get("no_vectors"), bool): raise ValueError("invalid updater configuration")
    if type(cfg.get("interval_min")) is not int or cfg["interval_min"] < 1: raise ValueError("invalid update interval")
    for key in ("clone_dir", "install_dir"): cfg[key] = str(Path(cfg[key]).expanduser().resolve())


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
    clone = Path(cfg["clone_dir"]).resolve()
    if clone == ROOT.resolve(): raise RuntimeError("refusing the working checkout as a maintenance clone")
    if clone.exists(): return verify_clone(clone, cfg["repo"], ROOT, git)
    clone.parent.mkdir(parents=True, exist_ok=True)
    log("creating updater-owned clone")
    res = subprocess.run(["git", "clone", "--branch", cfg["branch"], "--single-branch", "--", cfg["repo"], str(clone)], capture_output=True, text=True, timeout=900, check=False)
    if res.returncode: raise RuntimeError("git clone failed")
    mark_clone(clone, cfg["repo"])
    return verify_clone(clone, cfg["repo"], ROOT, git)


def upstream_commit(cfg: dict) -> str:
    clone = ensure_clone(cfg)
    res = git(["fetch", "--quiet", "origin", f"+refs/heads/{cfg['branch']}:refs/remotes/origin/{cfg['branch']}"], clone)
    if res.returncode != 0:
        raise RuntimeError("git fetch failed")
    res = git(["rev-parse", "--short=12", f"origin/{cfg['branch']}"], clone)
    if res.returncode or not re.fullmatch(r"[0-9a-f]{12,40}", res.stdout.strip()): raise RuntimeError("upstream revision lookup failed")
    return res.stdout.strip()


def checkout_upstream(cfg: dict) -> str:
    clone = ensure_clone(cfg)
    res = git(["reset", "--hard", f"origin/{cfg['branch']}"], clone)
    if res.returncode != 0:
        raise RuntimeError("git reset failed")
    revision = git(["rev-parse", "--short=12", "HEAD"], clone)
    if revision.returncode or not re.fullmatch(r"[0-9a-f]{12,40}", revision.stdout.strip()): raise RuntimeError("checkout revision lookup failed")
    return revision.stdout.strip()


def build_from_clone(cfg: dict, destination: Path | None = None) -> Path:
    clone = Path(cfg["clone_dir"])
    argv = [cfg["python"], str(clone / "scripts" / "package_chrome_extension.py")]
    if cfg.get("no_vectors"):
        argv.append("--no-vectors")
    env = dict(os.environ)
    env["MDBX_CORPUS"] = str(clone / "corpus")
    # the clone's own index: built once, then reused (vectors need Ollama; keyword-only otherwise)
    db = clone / "data" / "mdbx.sqlite"
    env["MDBX_DB"] = str(db)
    if any(path.is_symlink() for path in [clone / "corpus", db.parent, db]):
        raise RuntimeError("clone corpus or index destination is a symlink")
    if not db.exists():
        log("building the clone's search index (first run)")
        index_command = [cfg["python"], "-m", "mdbx.cli", "index"]
        if cfg.get("no_vectors"): index_command.append("--skip-semantic")
        idx = subprocess.run(index_command, cwd=str(clone), env=env,
                             capture_output=True, text=True, timeout=3600, check=False)
        if idx.returncode not in (0, 1):  # 1 = keyword index built, Ollama absent
            raise RuntimeError("mdbx index failed")
    log("packaging the extension from the clone")
    res = subprocess.run(argv, cwd=str(clone), env=env, capture_output=True, text=True, timeout=1800, check=False)
    if res.returncode != 0:
        raise RuntimeError("package script failed")
    log("extension package prepared")
    manifest = json.loads(safe_bytes(clone / "editors/chrome/manifest.json", clone))
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}", version): raise RuntimeError("invalid packaged version")
    output = destination or Path(tempfile.mkdtemp(prefix="mdbx-built-extension-"))
    unpack_archive(clone / "dist" / f"mongodb-expertise-chrome-{version}.zip", output)
    return output


# ---- release source ----
def release_commit(cfg: dict) -> str:
    """Commit recorded in the CI release's build.json (downloaded to a temp dir)."""
    with tempfile.TemporaryDirectory(prefix="mdbx-rel-") as tmp:
        res = subprocess.run(["gh", "release", "download", RELEASE_TAG, "--repo", repo_slug(cfg["repo"]),
                              "--pattern", "build.json", "--dir", tmp, "--clobber"],
                             capture_output=True, text=True, timeout=120, check=False)
        if res.returncode != 0:
            raise RuntimeError("gh release download failed")
        stamp = json.loads(Path(tmp, "build.json").read_text(encoding="utf-8"))
    return str(stamp.get("commit") or "")


def download_release(cfg: dict, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(["gh", "release", "download", RELEASE_TAG, "--repo", repo_slug(cfg["repo"]),
                          "--pattern", RELEASE_ASSET, "--dir", str(dest), "--clobber"],
                         capture_output=True, text=True, timeout=600, check=False)
    if res.returncode != 0:
        raise RuntimeError("gh release download failed")
    unpacked = dest / "unpacked"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    unpack_archive(dest / RELEASE_ASSET, unpacked)
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


def unpack_archive(path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            rel = Path(info.filename)
            if rel.is_absolute() or ".." in rel.parts or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("unsafe extension archive entry")
        archive.extractall(destination)


def validate_runtime(src: Path) -> list[Path]:
    try:
        manifest = json.loads(safe_bytes(src / "manifest.json", src))
        if not isinstance(manifest, dict) or manifest.get("manifest_version") != 3 or not isinstance(manifest.get("version"), str): raise ValueError()
        files = runtime_files(src)
        for name in RUNTIME_FILES: safe_bytes(src / name, src)
        declared = list(manifest.get("icons", {}).values())
        if manifest.get("background", {}).get("service_worker"): declared.append(manifest["background"]["service_worker"])
        if manifest.get("action", {}).get("default_popup"): declared.append(manifest["action"]["default_popup"])
        for name in declared:
            if not isinstance(name, str): raise TypeError()
            safe_bytes(src / name, src)
        stamp = json.loads(safe_bytes(src / "data/build.json", src))
        if not isinstance(stamp, dict) or not build_id(stamp) or stamp.get("version") != manifest["version"]: raise ValueError()
        for path in files: safe_bytes(path, src)
        return files
    except (OSError, ValueError, TypeError, KeyError):
        raise RuntimeError("extension runtime is incomplete or invalid") from None


def recover_install(install: Path, journal: Path) -> None:
    if not journal.exists(): return
    try:
        state = json.loads(journal.read_text())
        backup, stage = Path(state["backup"]), Path(state["stage"])
        for path, prefix in [(backup, "." + install.name + ".backup-"), (stage, "." + install.name + ".stage-")]:
            if path.parent != install.parent or not path.name.startswith(prefix) or path.is_symlink(): raise ValueError()
    except (ValueError, KeyError, TypeError): raise RuntimeError("ambiguous extension swap journal; preserve it for recovery") from None
    if not install.exists() and backup.exists(): os.rename(backup, install)
    if not install.exists(): raise RuntimeError("incomplete extension swap; backup preserved")
    # Journal paths were created by this updater under the install lock.
    if stage.exists(): shutil.rmtree(stage)
    if backup.exists(): shutil.rmtree(backup)
    journal.unlink()


def sync_runtime(src: Path, install_dir: Path) -> int:
    """Stage and validate an owned replacement; roll back if publishing the staged directory fails."""
    install_dir = Path(install_dir).absolute(); install_dir.parent.mkdir(parents=True, exist_ok=True)
    if install_dir.is_symlink(): raise RuntimeError("installation directory is a symlink")
    files = validate_runtime(src)
    journal = install_dir.with_name("." + install_dir.name + ".swap.json")
    recover_install(install_dir, journal)
    stage = Path(tempfile.mkdtemp(prefix="." + install_dir.name + ".stage-", dir=install_dir.parent))
    backup = Path(tempfile.mkdtemp(prefix="." + install_dir.name + ".backup-", dir=install_dir.parent)); backup.rmdir()
    published = False
    try:
        for path in files:
            target = stage / path.relative_to(src); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(safe_bytes(path, src))
        validate_runtime(stage)
        atomic_write(journal, json.dumps({"backup": str(backup), "stage": str(stage)}).encode(), 0o600)
        if install_dir.exists(): os.rename(install_dir, backup)
        try: os.rename(stage, install_dir)
        except OSError:
            if backup.exists() and not install_dir.exists(): os.rename(backup, install_dir)
            raise
        published = True
        if backup.exists(): shutil.rmtree(backup)
        journal.unlink()
    finally:
        if stage.exists(): shutil.rmtree(stage)
        if not published and install_dir.exists() and not backup.exists(): journal.unlink(missing_ok=True)
    return len(files)


def run_update(cfg: dict, *, force: bool = False) -> int:
    clone, install = Path(cfg["clone_dir"]), Path(cfg["install_dir"])
    try:
        with lock(clone.with_name("." + clone.name + ".chrome-update.lock")), lock(install.with_name("." + install.name + ".install.lock")):
            return _run_update(cfg, force=force)
    except RuntimeError as error:
        if str(error) != "maintenance operation is busy": raise
        log("busy: another extension update is active"); return 0


def _run_update(cfg: dict, *, force: bool = False) -> int:
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
        with tempfile.TemporaryDirectory(prefix="mdbx-local-build-") as output:
            src = build_from_clone(cfg, destination=Path(output))
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
    print("Running the first update now…")
    try:
        run_update(cfg, force=not Path(cfg["install_dir"]).exists())
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError):
        print("first update failed", file=sys.stderr)
        return 1
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(AGENT_PLIST)], capture_output=True, check=False)
    res = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT_PLIST)], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print("launchctl bootstrap failed", file=sys.stderr)
        return 1
    print(f"agent installed: {AGENT_PLIST} (every {cfg['interval_min']} min, source={cfg['source']})")
    print(f"config:          {CONFIG_PATH}")
    print(f"log:             {LOG_PATH}")
    print(f"extension dir:   {cfg['install_dir']}")
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
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError):
        target = "? (upstream lookup failed)"
    agent = "installed" if AGENT_PLIST.exists() else "not installed"
    print(json.dumps({"install_dir": cfg["install_dir"], "installed_build": build_id(installed) or None,
                      "installed_version": installed.get("version"), "built_at": installed.get("built_at"),
                      "upstream": target, "source": cfg["source"], "repo": scrub(cfg["repo"]), "branch": cfg["branch"],
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
    raw = list(sys.argv[1:] if argv is None else argv)
    front, rest = [], []
    values = {"--repo", "--branch", "--clone-dir", "--python", "--interval-min", "--install-dir", "--source"}
    while raw:
        token = raw.pop(0)
        if token in values:
            front.append(token)
            if raw: front.append(raw.pop(0))
        elif token.split("=", 1)[0] in values or token == "--no-vectors": front.append(token)
        else: rest.append(token)
    a = ap.parse_args(front + rest)
    try:
        cfg = effective_config(a)
        if a.cmd == "install-agent":
            return install_agent(cfg)
        if a.cmd == "uninstall-agent":
            return uninstall_agent()
        if a.cmd == "status":
            return status(cfg)
        return run_update(cfg, force=a.force)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        log(f"error: {type(exc).__name__}; maintenance operation failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
