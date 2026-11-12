#!/usr/bin/env python3
"""Redact customer and internal-tooling references from the corpus copies, in place.

Idempotent. Run by scripts/sync_corpus.sh after copying. Two rule sets:

* generic rules (this file): local paths, private ticket keys, internal hostnames, generator comments;
* private rules (NOT in the repo): ``$MDBX_REDACTIONS`` or ``~/.config/mdbx/redactions.py`` defining
  ``RULES`` (exact-phrase pairs, may name customers) and optionally ``PATCH`` (path to a unified diff of
  hand edits, applied last with ``patch -p1`` from the repo root).

Files that cannot be redacted are listed in PRIVATE_FILES and in .gitignore; they are never committed.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import replace_preserving, safe_bytes

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"

#: Exact files/dirs that stay local-only because redaction cannot make them safe.
PRIVATE_FILES = [
    "corpus/llms/uber-mongodb-skill.md",
    "corpus/llms/memory-central/",
    "corpus/skills/atlas-diagnostics-expert/SKILL.md",
    "corpus/skills/atlas-diagnostics-expert/references/atlas-diagnostics-package.md",
    "corpus/skills/mongodb-ts-diag-and-diagnostic-workflows/",
    "corpus/llms/ts-diag-and-diagnostic-workflows.llms/",
    "corpus/skills/mongodb-kb-backed-troubleshooting/",
    "corpus/llms/kb-backed-troubleshooting.llms/",
]

#: (pattern, replacement) applied with re.sub to every text file.
GENERIC_REGEX: list[tuple[re.Pattern, str]] = [
    # stop at quotes/brackets so a path inside JSON or a markdown link keeps its closing delimiter
    (re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s\\\"'`)\]>},]*"), "<local-path>"),
    (re.compile(r"~/\.(?:claude|global-ai-hub)/[^\s\\\"'`)\]>},]*"), "<local-path>"),
    (re.compile(r"[ \t]*\(HELP-\d+\)"), ""),
    (re.compile(r"\bHELP-\d+\b"), "<ticket>"),
    (re.compile(r"(?<![\w.-])[\w.-]*\.corp\.mongodb\.com\b", re.IGNORECASE), "internal.example.com"),
    (re.compile(r"^<!--[^\n]*skill-to-llms-txt[^\n]*-->\n", re.MULTILINE), ""),
]


def load_private() -> tuple[list[tuple[str, str]], str | None]:
    path = Path(os.environ.get("MDBX_REDACTIONS", Path.home() / ".config/mdbx/redactions.py"))
    if not path.is_file():
        print("note: selected private redaction rules are unavailable; generic rules only", file=sys.stderr)
        return [], None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec = importlib.util.spec_from_file_location("mdbx_private_redactions", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rules = getattr(mod, "RULES", [])
            patch = getattr(mod, "PATCH", None)
        if not isinstance(rules, (list, tuple)) or any(not isinstance(rule, (list, tuple)) or len(rule) != 2 or not isinstance(rule[0], str) or not rule[0] or not isinstance(rule[1], str) for rule in rules):
            raise ValueError()
        if patch is not None and not isinstance(patch, str):
            raise ValueError()
        return list(rules), patch
    except (Exception, SystemExit):  # noqa: BLE001 - private executable configuration must not escape
        raise ValueError("private redaction configuration is invalid") from None


def redact_text(text: str, rules: list[tuple[str, str]]) -> str:
    for old, new in rules:
        text = text.replace(old, new)
    for pat, new in GENERIC_REGEX:
        text = pat.sub(new, text)
    return text


def is_private(rel: str) -> bool:
    return any(rel == f.rstrip("/") or (f.endswith("/") and rel.startswith(f)) for f in PRIVATE_FILES)


def recovery_directory() -> Path:
    # Linked-worktree .git files are deliberately unsupported; do not trust their external path.
    root_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        git_fd = os.open(".git", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            try:
                os.mkdir("mdbx-redaction-recovery", 0o700, dir_fd=git_fd)
            except FileExistsError:
                pass
            recovery_fd = os.open("mdbx-redaction-recovery", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=git_fd)
            try:
                os.fchmod(recovery_fd, 0o700)
            finally:
                os.close(recovery_fd)
        finally:
            os.close(git_fd)
    finally:
        os.close(root_fd)
    return ROOT / ".git/mdbx-redaction-recovery"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path)
    args = parser.parse_args([] if argv is None else argv)
    corpus = args.corpus or CORPUS
    if corpus.is_symlink() or not corpus.is_dir():
        print("error: corpus copy is outside the repository", file=sys.stderr); return 1
    try:
        rules, patch = load_private()
    except ValueError:
        print("error: private redaction configuration is invalid", file=sys.stderr); return 1
    if any(not isinstance(old, str) or not old or not isinstance(new, str) for old, new in rules):
        print("error: invalid private redaction rule", file=sys.stderr); return 1
    replacements = [new for _, new in rules] + [new for _, new in GENERIC_REGEX]
    if any(old in new for old, _ in rules for new in replacements):
        print("error: private redaction rules can reintroduce matches", file=sys.stderr); return 1
    plan = []
    errors = 0
    for p in sorted(corpus.rglob("*")):
        rel = "corpus/" + p.relative_to(corpus).as_posix()
        if p.is_symlink():
            print("error: symlink in redaction input", file=sys.stderr); errors += 1; continue
        if not p.is_file() or p.suffix.lower() not in {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv"}: continue
        if is_private(rel) or rel.startswith(("corpus/recipes/", "corpus/llms/mongodb.com.llms/")): continue
        try:
            original = safe_bytes(p, corpus); old = original.decode("utf-8"); new = redact_text(old, rules)
            if redact_text(new, rules) != new: raise ValueError("non-idempotent redaction")
        except (OSError, UnicodeError, ValueError):
            print("error: unreadable or non-idempotent redaction input", file=sys.stderr); errors += 1; continue
        if new != old: plan.append((p, original, new.encode("utf-8")))
    if errors: return 1
    if patch and not Path(patch).is_file():
        print("error: configured private patch is missing", file=sys.stderr); return 1
    try:
        recovery_root = recovery_directory() if plan else None
    except (OSError, ValueError):
        print("error: private recovery storage is unavailable; source preserved", file=sys.stderr); return 1
    for p, original, new in plan:
        try:
            if safe_bytes(p, corpus) != original:
                print("error: redaction input changed; retry", file=sys.stderr); return 1
            recovery = replace_preserving(p, new, corpus, original, p.stat().st_mode & 0o777)
            try:
                recovery.move_to(recovery_root)
            finally:
                recovery.close()
        except (OSError, ValueError, RuntimeError):
            print("error: redaction publication failed; source or recovery data preserved", file=sys.stderr); return 1
    # Check each file patch independently so refreshed and already-patched families can coexist.
    if patch:
        try:
            payload = Path(patch).read_bytes()
            pieces = re.split(rb"(?m)(?=^diff --git )" if re.search(rb"(?m)^diff --git ", payload) else rb"(?m)(?=^--- [^\n]+\n\+\+\+ )", payload)
            pieces = [piece for piece in pieces if piece.strip() and (piece.startswith(b"diff --git ") or b"--- " in piece)]
            if not pieces:
                raise ValueError()
            pending = []
            for piece in pieces:
                options = {"cwd": corpus.parent, "input": piece, "capture_output": True, "timeout": 30}
                forward = subprocess.run(["git", "apply", "--check", "-"], check=False, **options)
                if forward.returncode == 0:
                    pending.append(piece)
                elif subprocess.run(["git", "apply", "--reverse", "--check", "-"], check=False, **options).returncode:
                    raise ValueError()
            applied = []
            for piece in pending:
                if subprocess.run(["git", "apply", "-"], cwd=corpus.parent, input=piece, capture_output=True, timeout=30, check=False).returncode:
                    raise ValueError()
                applied.append(piece)
            for path in sorted(corpus.rglob("*")):
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv"}:
                    content = safe_bytes(path, corpus).decode("utf-8")
                    if redact_text(content, rules) != content:
                        raise ValueError()
        except (OSError, UnicodeError, ValueError, subprocess.SubprocessError):
            for piece in reversed(locals().get("applied", [])):
                subprocess.run(["git", "apply", "--reverse", "-"], cwd=corpus.parent, input=piece, capture_output=True, timeout=30, check=False)
            print("error: configured private patch rejected", file=sys.stderr); return 1
    print(f"{len(plan)} file(s) changed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
