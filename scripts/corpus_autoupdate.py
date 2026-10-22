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
pass warns when they are missing, because then only the built-in markers are checked. Log:
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
STATE_KEYS = ("repo", "branch", "clone_dir", "python", "interval_min")
HIT_RE = re.compile(r"^(corpus/[^:]+):\d+:")


def log(msg: str) -> None:
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
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
    cfg.setdefault("repo", origin_url() or DEFAULT_REPO)
    cfg.setdefault("branch", "main")
    cfg.setdefault("clone_dir", str(DEFAULT_CLONE_DIR))
    cfg.setdefault("python", sys.executable)
    cfg.setdefault("interval_min", 360)
    return cfg


def git(args: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)


def must_git(args: list[str], cwd: Path, what: str) -> str:
    res = git(args, cwd)
    if res.returncode != 0:
        raise RuntimeError(f"{what} failed: {(res.stderr or res.stdout).strip()[-400:]}")
    return res.stdout


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


def reset_to_origin(clone: Path, branch: str) -> None:
    must_git(["fetch", "--quiet", "origin", branch], clone, "git fetch")
    must_git(["reset", "--hard", f"origin/{branch}"], clone, "git reset")
    must_git(["clean", "-fdq", "corpus"], clone, "git clean")


def sweep(clone: Path, python: str) -> tuple[int, list[str]]:
    res = subprocess.run([python, str(clone / "scripts" / "sweep_customers.py")], cwd=str(clone),
                         capture_output=True, text=True, timeout=600, check=False)
    files = sorted({m.group(1) for ln in (res.stdout + res.stderr).splitlines() if (m := HIT_RE.match(ln))})
    return res.returncode, files


def restore_committed(clone: Path, files: list[str]) -> None:
    """Put each file back to its committed text; delete the ones that are new."""
    for rel in files:
        tracked = git(["ls-files", "--error-unmatch", rel], clone).returncode == 0
        if tracked:
            must_git(["checkout", "HEAD", "--", rel], clone, f"git checkout {rel}")
        else:
            (clone / rel).unlink(missing_ok=True)
        log(f"  held back {rel} ({'kept committed text' if tracked else 'new file dropped'})")


def run_update(cfg: dict, *, dry_run: bool = False) -> int:
    clone = ensure_clone(cfg)
    reset_to_origin(clone, cfg["branch"])
    py = cfg["python"]
    denylist = Path(os.environ.get("MDBX_DENYLIST", HOME / ".config" / "mdbx" / "denylist.txt"))
    if not denylist.is_file():  # built-in markers do not catch customer names; refuse to publish without the list
        log(f"abort: customer denylist {denylist} missing; nothing synced")
        return 1
    if not (HOME / ".config" / "mdbx" / "redactions.py").is_file():
        log("warning: ~/.config/mdbx/redactions.py missing; only generic redaction rules apply")
    env = dict(os.environ, MDBX_SKIP_INDEX="1")
    sync = subprocess.run(["bash", str(clone / "scripts" / "sync_corpus.sh")], cwd=str(clone), env=env,
                          capture_output=True, text=True, timeout=1800, check=False)
    tail = (sync.stderr or sync.stdout).strip().splitlines()[-1:] or [""]
    log(f"sync_corpus.sh exit {sync.returncode}: {tail[0][:200]}")
    # the script's own sweep may have stopped it before finishing; redaction ran first, so go on to the gate.
    restore_committed(clone, [p for p in PROTECTED if (clone / p).exists()])
    for attempt in (1, 2):
        rc, hits = sweep(clone, py)
        if rc == 0:
            break
        if attempt == 2 or not hits:
            log(f"abort: sweep still reports markers ({len(hits)} files); nothing committed")
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
        raise RuntimeError(f"git pull --rebase failed: {pull.stderr.strip()[-300:]}")
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
                                 "MDBX_CORPUS_AUTOUPDATE_CONFIG": str(CONFIG_PATH)},
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
        print(f"launchctl bootstrap failed: {res.stderr.strip()}", file=sys.stderr)
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
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        last = lines[-1] if lines else ""
    except OSError:
        pass
    print(json.dumps({"agent": "installed" if AGENT_PLIST.exists() else "not installed", "repo": cfg["repo"],
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
    a = ap.parse_args(argv)
    cfg = effective_config(a)
    try:
        if a.cmd == "install-agent":
            return install_agent(cfg)
        if a.cmd == "uninstall-agent":
            return uninstall_agent()
        if a.cmd == "status":
            return status(cfg)
        return run_update(cfg, dry_run=a.dry_run)
    except (RuntimeError, subprocess.SubprocessError) as exc:
        log(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
