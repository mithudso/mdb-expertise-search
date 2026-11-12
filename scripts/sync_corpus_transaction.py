#!/usr/bin/env python3
"""Prepare and privacy-check a complete corpus generation before publishing it."""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import redact_corpus
import sweep_customers
from maintenance_safety import atomic_write, exchange_entries, git_environment, lock, safe_bytes
from sync_corpus_sources import check_publication, sync_tree

ROOT = Path(__file__).resolve().parent.parent
LLMS_FAMILIES = ['atlas-cli', 'atlas-triage-workflows', 'diagnostic-tool-design', 'error-codes-and-troubleshooting', 'ftdc-and-log-tooling', 'kb-backed-troubleshooting', 'mongodb-atlas-data-federation', 'mongodb-drivers', 'mongosh-reference', 'ts-diag-and-diagnostic-workflows']


def identity(path):
    try:
        info = path.stat(follow_symlinks=False)
        return [info.st_dev, info.st_ino]
    except FileNotFoundError:
        return None


def private_recovery():
    root_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        git_fd = os.open(".git", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            try:
                os.mkdir("mdbx-corpus-recovery", 0o700, dir_fd=git_fd)
            except FileExistsError:
                pass
            handle = os.open("mdbx-corpus-recovery", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=git_fd)
            try:
                os.fchmod(handle, 0o700)
            finally:
                os.close(handle)
        finally:
            os.close(git_fd)
    finally:
        os.close(root_fd)
    return ROOT / ".git/mdbx-corpus-recovery"


def paths():
    return ROOT / "data/corpus-sync-owned.json", ROOT / "data/.corpus-sync-journal.json"


def recover():
    state_path, journal = paths()
    if not journal.exists():
        return
    row = json.loads(safe_bytes(journal, ROOT, max_bytes=1024 * 1024))
    token = row["token"]
    if not isinstance(token, str) or len(token) != 32 or any(ch not in "0123456789abcdef" for ch in token):
        raise ValueError("ambiguous corpus publication")
    stage = ROOT / (".mdbx-corpus-preparation-" + token)
    prepared = ROOT / (".mdbx-corpus-stage-" + token)
    marker = json.loads(safe_bytes(stage / "owner.json", ROOT, max_bytes=4096))
    if marker != {"root": str(ROOT), "token": token}:
        raise ValueError("ambiguous corpus publication")
    current = identity(ROOT / "corpus")
    if current == row["new_identity"]:
        atomic_write(state_path, safe_bytes(stage / "state.after", ROOT), 0o600, root=ROOT)
        if prepared.exists():
            destination = private_recovery() / token
            destination.mkdir(mode=0o700)
            src_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            dst_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.rename(prepared.name, "corpus", src_dir_fd=src_fd, dst_dir_fd=dst_fd)
            finally:
                os.close(src_fd)
                os.close(dst_fd)
            atomic_write(destination / "ownership.before", safe_bytes(stage / "state.before", ROOT), 0o600, root=destination)
    elif current == row["old_identity"]:
        if row["had_state"]:
            atomic_write(state_path, safe_bytes(stage / "state.before", ROOT), 0o600, root=ROOT)
        else:
            state_path.unlink(missing_ok=True)
        if prepared.exists():
            shutil.rmtree(prepared)
    else:
        raise RuntimeError("corpus generation changed; publication recovery preserved")
    journal.unlink()
    shutil.rmtree(stage)


def prepare(stage):
    corpus = stage / "corpus"
    current = ROOT / "corpus"
    if current.is_symlink():
        raise ValueError("corpus root is unsafe")
    if current.exists():
        shutil.copytree(current, corpus, symlinks=True)
    else:
        corpus.mkdir()
    ignore = ROOT / ".gitignore"
    if ignore.exists():
        (stage / ".gitignore").write_bytes(safe_bytes(ignore, ROOT))
    state_path, _journal = paths()
    before = safe_bytes(state_path, ROOT) if state_path.exists() else b"{}\n"
    (stage / "state.before").write_bytes(before)
    (stage / "state.after").write_bytes(before)
    def copy(source, destination, *, facts_only=False):
        sync_tree(source, corpus / destination, stage / "state.after", facts_only=facts_only,
                  identity_destination=ROOT / "corpus" / destination)
    skills = Path(os.environ.get("MDBX_SKILLS_SRC", Path.home() / ".claude/skills"))
    for source in [*sorted(skills.glob("mongodb-*")), skills / "atlas-diagnostics-expert", skills / "atlas-vector-search-pii-isolation"]:
        if source.is_dir():
            copy(source, Path("skills") / source.name)
    llms = Path(os.environ.get("MDBX_LLMS_SRC", Path.home() / "dev/skills-explorer/llms"))
    for name in LLMS_FAMILIES:
        source = llms / (name + ".llms")
        if source.is_dir():
            copy(source, Path("llms") / source.name)
    docs = Path(os.environ.get("MDBX_MONGODB_DOCS_LLMS", Path.home() / "dev/llms-explorer/outputs/exports/mongodb.com.llms"))
    if docs.is_dir():
        copy(docs, Path("llms") / docs.name)
    concepts = Path(os.environ.get("MDBX_CONCEPTS_SRC", Path.home() / ".global-ai-hub/llms-concepts"))
    for source in sorted(concepts.glob("mongodb-*.llms")):
        if source.is_dir() and source.name not in {"mongodb-atlas-data-federation.llms", "mongodb-drivers.llms"}:
            copy(source, Path("llms") / source.name, facts_only=True)
    return corpus


def run():
    state_path, journal = paths()
    with lock(ROOT / ".mdbx-corpus-sync.lock"):
        recover()
        deny = Path(os.environ.get("MDBX_DENYLIST", Path.home() / ".config/mdbx/denylist.txt"))
        if not deny.is_file():
            raise ValueError("privacy denylist is unavailable")
        # Fail before generation publication if private recovery storage is unsupported.
        private_recovery()
        token = uuid.uuid4().hex
        stage = ROOT / (".mdbx-corpus-preparation-" + token)
        stage.mkdir(mode=0o700)
        (stage / "owner.json").write_text(json.dumps({"root": str(ROOT), "token": token}))
        prepared = ROOT / (".mdbx-corpus-stage-" + token)
        try:
            with tempfile.TemporaryFile(mode="w+t") as output, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                corpus = prepare(stage)
                redact_corpus.ROOT = ROOT
                if redact_corpus.main(["--corpus", str(corpus)]) != 0:
                    raise ValueError("staged redaction failed")
                check_publication(corpus, repository=ROOT)
                sweep_customers.ROOT = ROOT
                if sweep_customers.main(["--corpus", str(corpus), "--json"]) != 0:
                    raise ValueError("staged privacy gate failed; candidate withheld")
            # The complete candidate is now gated. Publication never exposes raw input.
            old_identity = identity(ROOT / "corpus")
            os.rename(corpus, prepared)
            row = {"token": token, "old_identity": old_identity, "new_identity": identity(prepared),
                   "had_state": state_path.exists()}
            with lock(state_path.with_suffix(".lock")):
                before = safe_bytes(state_path, ROOT) if state_path.exists() else b"{}\n"
                if before != safe_bytes(stage / "state.before", ROOT):
                    raise RuntimeError("corpus ownership state changed; candidate withheld")
                atomic_write(journal, json.dumps(row).encode(), 0o600, root=ROOT)
                atomic_write(state_path, safe_bytes(stage / "state.after", ROOT), 0o600, root=ROOT)
                if old_identity is None:
                    os.rename(prepared, ROOT / "corpus")
                else:
                    exchange_entries(prepared, ROOT / "corpus", ROOT)
                recover()
        finally:
            if not journal.exists():
                if prepared.exists():
                    shutil.rmtree(prepared)
                if stage.exists():
                    shutil.rmtree(stage)
    print("corpus generation passed privacy gates and was published")
    if os.environ.get("MDBX_SKIP_INDEX") != "1":
        subprocess.run([str(ROOT / ".venv/bin/mdbx"), "index", "--corpus", str(ROOT / "corpus")],
                       cwd=ROOT, env=git_environment(), timeout=3600, check=True)
    return 0


def main():
    try:
        return run()
    except (OSError, UnicodeError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError):
        print("corpus sync failed; candidate withheld and private diagnostics suppressed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
