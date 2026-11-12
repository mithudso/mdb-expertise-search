#!/usr/bin/env python3
"""Keep the committed ``corpus/`` copy current with the author's local skill and llms sources.

The corpus is a *copy* (people clone this repo from GitHub and get everything), so something on the
machine that holds the sources has to refresh it. A launchd agent runs ``run`` on a schedule. Each pass:

1. fetches the agent's own clone of the repo and resets it to ``origin/<branch>`` (your working
   checkout is never touched);
2. runs ``scripts/sync_corpus.sh`` there with ``MDBX_SKIP_INDEX=1`` (rsync from the skill tree, the
   skills-explorer exports and every ``mongodb-*.llms`` concept family; then redact);
3. sweeps for customer/internal markers. A file with a hit is put back to its last committed (clean)
   version, or deleted when new. The pass aborts without committing if hits remain;
4. commits only ``corpus/`` and pushes. Nothing changed means no commit.

    python scripts/corpus_autoupdate.py install-agent [--interval-min 360]
    python scripts/corpus_autoupdate.py run [--dry-run]    # one pass (what the agent runs)
    python scripts/corpus_autoupdate.py status
    python scripts/corpus_autoupdate.py uninstall-agent

Source locations come from the ``MDBX_*_SRC`` variables ``sync_corpus.sh`` documents. Private redaction
rules and the customer denylist stay in ``~/.config/mdbx/`` (``redactions.py``, ``denylist.txt``); the
pass aborts if the denylist is missing and warns if private redaction rules are missing. Log:
``~/Library/Logs/mdbx-corpus-autoupdate.log``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import confined_corpus_path, lock, mark_clone, scrub, verify_clone

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
CONFIG_PATH = Path(os.environ.get("MDBX_CORPUS_AUTOUPDATE_CONFIG", HOME / ".config" / "mdbx" / "corpus-autoupdate.json"))
DEFAULT_CLONE_DIR = HOME / "Library" / "Caches" / "mdbx" / "corpus-autoupdate" / "repo"
LOG_PATH = HOME / "Library" / "Logs" / "mdbx-corpus-autoupdate.log"
AGENT_LABEL = "com.mdbx.corpus-autoupdate"
AGENT_PLIST = HOME / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"
DEFAULT_REPO = "https://github.com/mithudso/mdb-expertise-search.git"
#: Files whose live source cites private workload analyses: only ever kept at their committed, hand-redacted text.
PROTECTED = ["corpus/skills/mongodb-expert/references/deep-mongodb-mql-query-optimizer.md"]
STATE_KEYS = ("repo", "branch", "clone_dir", "python", "interval_min", "environment")
HIT_RE = re.compile(r"^(corpus/[^:]+):\d+:")


def log(msg: str) -> None:
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {scrub(msg)}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({k: cfg[k] for k in STATE_KEYS if k in cfg}, indent=2) + "\n", encoding="utf-8")


def origin_url() -> str:
    res = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"], capture_output=True, text=True,
                         timeout=10, check=False)
    return res.stdout.strip()


def effective_config(args) -> dict:
    cfg = load_config()
    for key in STATE_KEYS:
        val = getattr(args, key, None)
        if val is not None:
            cfg[key] = str(val) if isinstance(val, Path) else val
    if "repo" not in cfg: cfg["repo"] = origin_url() or DEFAULT_REPO
    cfg.setdefault("branch", "main")
    cfg.setdefault("clone_dir", str(DEFAULT_CLONE_DIR))
    cfg.setdefault("python", sys.executable)
    cfg.setdefault("interval_min", 360)
    validate_config(cfg)
    return cfg


SOURCE_ENV = ("MDBX_DENYLIST", "MDBX_REDACTIONS", "MDBX_SKILLS_SRC", "MDBX_LLMS_SRC", "MDBX_MONGODB_DOCS_LLMS", "MDBX_CONCEPTS_SRC")

def validate_config(cfg):
    for key in ("repo", "branch", "clone_dir", "python"):
        if not isinstance(cfg.get(key), str) or not cfg[key].strip(): raise ValueError("invalid updater configuration")
    if type(cfg.get("interval_min")) is not int or cfg["interval_min"] < 1: raise ValueError("invalid update interval")
    cfg["clone_dir"] = str(Path(cfg["clone_dir"]).expanduser().resolve())
    environment = cfg.get("environment", {})
    if not isinstance(environment, dict) or any(k not in SOURCE_ENV or not isinstance(v, str) or not v for k, v in environment.items()): raise ValueError("invalid updater environment")
    cfg["environment"] = {**environment, **{key: str(Path(os.environ[key]).expanduser().resolve()) for key in SOURCE_ENV if os.environ.get(key)}}


def git(args: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)


def must_git(args: list[str], cwd: Path, what: str) -> str:
    res = git(args, cwd)
    if res.returncode != 0:
        raise RuntimeError(f"{what} failed")
    return res.stdout


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


def reset_to_origin(clone: Path, branch: str) -> None:
    must_git(["fetch", "--quiet", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}"], clone, "git fetch")
    must_git(["reset", "--hard", f"origin/{branch}"], clone, "git reset")
    must_git(["clean", "-fdq", "corpus"], clone, "git clean")


def sweep(clone: Path, python: str) -> tuple[int, list[str]]:
    res = subprocess.run([python, str(clone / "scripts" / "sweep_customers.py"), "--json"], cwd=str(clone),
                         capture_output=True, text=True, timeout=600, check=False, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    try:
        result = json.loads(res.stdout)
        if result.get("status") not in {"clean", "markers"} or res.returncode not in (0, 1): raise ValueError()
        files = result["files"]
        if not isinstance(files, list) or not all(isinstance(p, str) for p in files): raise ValueError()
        for rel in files: confined_corpus_path(clone, rel)
    except (ValueError, KeyError, TypeError, RuntimeError):
        log(f"sweep execution failed (exit {res.returncode})")
        return 2, []
    return res.returncode, files


def restore_committed(clone: Path, files: list[str]) -> None:
    """Put each file back to its committed text; delete the ones that are new."""
    for rel in files:
        candidate = confined_corpus_path(clone, rel)
        tracked = git(["--literal-pathspecs", "ls-files", "--error-unmatch", "--", rel], clone).returncode == 0
        if tracked:
            must_git(["--literal-pathspecs", "checkout", "HEAD", "--", rel], clone, f"git checkout {rel}")
        else:
            candidate.unlink(missing_ok=True)
        log(f"  held back {rel} ({'kept committed text' if tracked else 'new file dropped'})")


def run_update(cfg: dict, *, dry_run: bool = False) -> int:
    clone = Path(cfg["clone_dir"])
    try:
        with lock(clone.with_name("." + clone.name + ".corpus-update.lock")):
            return _run_update(cfg, dry_run=dry_run)
    except RuntimeError as error:
        if str(error) != "maintenance operation is busy": raise
        log("busy: another corpus update is active"); return 0


def _run_update(cfg: dict, *, dry_run: bool = False) -> int:
    clone = ensure_clone(cfg)
    reset_to_origin(clone, cfg["branch"])
    py = cfg["python"]
    denylist = Path(cfg.get("environment", {}).get("MDBX_DENYLIST", os.environ.get("MDBX_DENYLIST", HOME / ".config" / "mdbx" / "denylist.txt")))
    if not denylist.is_file():  # built-in markers do not catch customer names; refuse to publish without the list
        log(f"abort: customer denylist {denylist} missing; nothing synced")
        return 1
    if not (HOME / ".config" / "mdbx" / "redactions.py").is_file():
        log("warning: ~/.config/mdbx/redactions.py missing; only generic redaction rules apply")
    env = dict(os.environ, **cfg.get("environment", {}), MDBX_SKIP_INDEX="1", PYTHONDONTWRITEBYTECODE="1")
    sync = subprocess.run(["bash", str(clone / "scripts" / "sync_corpus.sh")], cwd=str(clone), env=env,
                          capture_output=True, text=True, timeout=1800, check=False)
    log(f"sync_corpus.sh exit {sync.returncode}")
    if sync.returncode:
        log("abort: source sync failed; nothing committed"); return 1
    restore_committed(clone, PROTECTED)
    for attempt in (1, 2):
        rc, hits = sweep(clone, py)
        if rc == 0:
            break
        if attempt == 2 or not hits:
            log(f"abort: sweep gate failed (exit {rc}, {len(hits)} marker files); nothing committed")
            reset_to_origin(clone, cfg["branch"])
            return 1
        log(f"sweep flagged {len(hits)} file(s); holding them back")
        restore_committed(clone, hits)
    status = must_git(["status", "--porcelain", "--", "corpus"], clone, "git status")
    changed = [ln for ln in status.splitlines() if ln.strip()]
    if not changed:
        log("corpus already current; nothing to commit")
        return 0
    new = sum(1 for ln in changed if ln.startswith("??"))
    log(f"{len(changed)} corpus path(s) changed ({new} new)")
    if dry_run:
        log("dry run: leaving the clone's changes uncommitted")
        return 0
    must_git(["add", "--", "corpus"], clone, "git add")
    msg = (f"corpus: refresh from local skills and llms sources ({dt.date.today().isoformat()})\n\n"
           f"{len(changed)} path(s) changed, {new} new. Automated by scripts/corpus_autoupdate.py; "
           "redacted and swept before commit.\n")
    must_git(["commit", "-q", "-m", msg], clone, "git commit")
    pull = git(["pull", "--rebase", "--quiet", "origin", cfg["branch"]], clone)
    if pull.returncode != 0:
        git(["rebase", "--abort"], clone)
        raise RuntimeError("git pull --rebase failed")
    rc, _hits = sweep(clone, py)
    if rc:
        log(f"abort: outgoing rebased tree failed sweep (exit {rc}); nothing pushed"); return 1
    must_git(["push", "origin", f"HEAD:{cfg['branch']}"], clone, "git push")
    log("pushed corpus refresh to origin/" + cfg["branch"])
    return 0


def agent_plist(cfg: dict) -> dict:
    return {
        "Label": AGENT_LABEL,
        "ProgramArguments": [cfg["python"], str(Path(__file__).resolve()), "run"],
        "StartInterval": int(cfg["interval_min"]) * 60,
        "RunAtLoad": False,
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "HOME": str(HOME),
                                 "MDBX_CORPUS_AUTOUPDATE_CONFIG": str(CONFIG_PATH), **cfg.get("environment", {})},
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
    res = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT_PLIST)], capture_output=True, text=True,
                         check=False)
    if res.returncode != 0:
        print("launchctl bootstrap failed", file=sys.stderr)
        return 1
    print(f"agent installed: {AGENT_PLIST} (every {cfg['interval_min']} min)")
    print(f"config: {CONFIG_PATH}\nlog:    {LOG_PATH}\nclone:  {cfg['clone_dir']}")
    print("Run one pass now with: python scripts/corpus_autoupdate.py run")
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
    last = ""
    try:
        with LOG_PATH.open("rb") as stream:
            stream.seek(0, 2); end = stream.tell(); size = min(end, 8192); stream.seek(end - size)
            lines = stream.read(size).decode("utf-8", errors="replace").splitlines(); last = lines[-1] if lines else ""
    except OSError:
        pass
    print(json.dumps({"agent": "installed" if AGENT_PLIST.exists() else "not installed", "repo": scrub(cfg["repo"]),
                      "branch": cfg["branch"], "clone_dir": cfg["clone_dir"], "interval_min": cfg["interval_min"],
                      "log": str(LOG_PATH), "last_log_line": last}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo")
    ap.add_argument("--branch")
    ap.add_argument("--clone-dir", dest="clone_dir", type=Path)
    ap.add_argument("--python", help="interpreter to run the sweep with (default: this one)")
    ap.add_argument("--interval-min", dest="interval_min", type=int)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install-agent")
    sub.add_parser("uninstall-agent")
    sub.add_parser("status")
    r = sub.add_parser("run", help="one refresh pass")
    r.add_argument("--dry-run", action="store_true")
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
        return run_update(cfg, dry_run=a.dry_run)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        log(f"error: {type(exc).__name__}; maintenance operation failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
