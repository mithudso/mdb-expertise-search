"""cli — the `mdbx` command."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import embed as embedmod
from . import index as idx
from . import search as srch


def _say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_index(args) -> int:
    con = idx.connect(args.db)
    root = Path(args.corpus) if args.corpus else idx.default_corpus()
    if not root.is_dir():
        _say(f"corpus not found: {root}")
        return 2
    if not args.skip_keyword:
        idx.build_keyword(con, root, _say)
    if not args.skip_semantic:
        try:
            idx.build_semantic(con, _say)
        except embedmod.EmbedError as exc:
            _say(f"semantic index skipped: {exc}")
            _say("keyword index is ready; start Ollama and re-run `mdbx index` to add vectors")
            return 1
    return 0


def _print_hit(i: int, h: srch.Hit, full: bool) -> None:
    print(f"{i:>2}. [{h.kind}] {h.source}  ·  {h.heading}")
    print(f"    {h.location}   score={h.score:.4f} via={h.via}")
    body = h.text if full else (h.snippet or " ".join(h.text.split())[:240])
    print("    " + body.replace("\n", "\n    "))
    print()


def cmd_search(args) -> int:
    con = idx.connect(args.db)
    if not idx.stats(con)["chunks"]:
        _say("index is empty — run `mdbx index` first")
        return 2
    notes: list[str] = []
    try:
        hits = srch.search(con, " ".join(args.query), args.mode, args.limit,
                           kind=args.kind, source=args.source, notes=notes)
    except embedmod.EmbedError as exc:
        _say(f"error: {exc}")
        _say("semantic search needs the embedder: start Ollama (`ollama serve`, model nomic-embed-text) "
             "or use `-m keyword`")
        return 1
    for n in notes:
        _say(f"warning: {n}")
    if args.json:
        print(json.dumps([{**h.__dict__, "location": h.location} for h in hits], indent=2))
        return 0
    if not hits:
        _say("no results")
        return 1
    for i, h in enumerate(hits, 1):
        _print_hit(i, h, args.full)
    return 0


def cmd_show(args) -> int:
    root = Path(args.corpus) if args.corpus else idx.default_corpus()
    p = (root / args.path).resolve()
    if root.resolve() not in p.parents or not p.is_file():
        _say(f"not a corpus file: {args.path}")
        return 2
    sys.stdout.write(p.read_text(encoding="utf-8", errors="replace"))
    return 0


def cmd_stats(args) -> int:
    con = idx.connect(args.db)
    s = idx.stats(con)
    if args.json:
        print(json.dumps(s, indent=2))
        return 0
    for k, v in s.items():
        print(f"{k:>12}: {v}")
    if args.sources:
        for r in con.execute(
            "SELECT source, kind, COUNT(*) n FROM chunks GROUP BY source, kind ORDER BY n DESC"
        ):
            print(f"  {r['n']:>6}  {r['kind']:<7} {r['source']}")
    return 0


def cmd_tui(args) -> int:
    try:
        from .tui import run
    except ImportError as exc:
        _say(str(exc))
        return 2
    run(args.db)
    return 0


def cmd_embed_fetch(args) -> int:
    from . import embed_onnx

    try:
        path = embed_onnx.fetch()
    except embed_onnx.OnnxUnavailable as exc:
        _say(str(exc))
        return 1
    print(f"in-process embedding model ready: {path}")
    print("Semantic search now works without Ollama (MDBX_EMBED_BACKEND=onnx forces it; default auto uses Ollama first).")
    return 0


def cmd_recipes(args) -> int:
    from . import recipes as rec

    items = rec.load()
    if args.query:
        q = " ".join(args.query).lower()
        items = [r for r in items if q in (r.name + " " + r.title + " " + r.summary).lower()]
    if args.json:
        print(json.dumps([{"name": r.name, "title": r.title, "summary": r.summary,
                           "applies_to": r.applies_to, "path": r.path} for r in items], indent=2))
        return 0
    if not items:
        _say("no recipes found")
        return 1
    width = max(len(r.name) for r in items)
    for r in items:
        tag = "/".join(r.applies_to) or "-"
        print(f"{r.name:<{width}}  [{tag}]  {r.summary}")
    return 0


def cmd_recipe(args) -> int:
    from . import recipes as rec

    found = rec.find(" ".join(args.name))
    if not found:
        _say(f"no recipe matches {' '.join(args.name)!r}; try `mdbx recipes`")
        return 1
    if len(found) > 1:
        _say("ambiguous; matches:")
        for r in found:
            _say(f"  {r.name}")
        return 1
    sys.stdout.write(found[0].text)
    return 0


def cmd_mcp(args) -> int:
    try:
        from .mcp_server import run
    except ImportError as exc:
        _say(f"{exc}\ninstall the MCP extra:  pip install 'mdb-expertise-search[mcp]'")
        return 2
    run()
    return 0


def cmd_lint(args) -> int:
    from .mql.analyze import analyze

    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    res = analyze(text)
    for d in res.diagnostics:
        line = text.count("\n", 0, d.start) + 1
        col = d.start - (text.rfind("\n", 0, d.start) + 1) + 1
        print(f"{args.file}:{line}:{col}: {d.severity}: {d.message} [{d.code}]")
    return 1 if any(d.severity == "error" for d in res.diagnostics) else 0


def cmd_export_web(args) -> int:
    from .webexport import export

    root = Path(args.corpus) if args.corpus else idx.default_corpus()
    db = Path(args.db) if args.db else idx.default_db()
    try:
        r = export(root, Path(args.out), db=db, vectors=not args.no_vectors, allow_untracked=args.allow_untracked)
    except RuntimeError as exc:
        print(f"mdbx export-web: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {r.out}: {r.chunks} chunks from {r.files} files, {r.terms} terms, {r.postings} postings, "
          f"{r.vectors} vectors" + (f"; skipped {r.skipped_untracked} untracked (private) files" if r.skipped_untracked else ""))
    return 0


def cmd_optimize(args) -> int:
    from .mql.optimize import format_report, optimize, to_dict

    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    rep = optimize(text, apply=not args.read_only)
    if args.json:
        print(json.dumps(to_dict(rep), indent=2))
    else:
        print(format_report(rep, args.file))
    if args.write and rep.changed and args.file != "-":
        Path(args.file).write_text(rep.text, encoding="utf-8")
        print(f"\nwrote rewritten queries to {args.file}", file=sys.stderr)
    return 1 if any(f.severity in {"blocking", "high"} for f in rep.findings) else 0


def cmd_auth(args) -> int:
    """`mdbx auth …` is the ai-auth CLI pinned to the mdbx namespace (see docs/INSTALLATION.md)."""
    from . import providers

    try:
        return providers.auth_cli(args.rest or ["status"])
    except providers.ProvidersUnavailable as exc:
        _say(str(exc))
        return 2


def cmd_ask(args) -> int:
    from . import providers

    if not providers.available():
        _say(providers.INSTALL_HINT)
        return 2
    import ai_auth

    question = " ".join(args.question)
    con = idx.connect(args.db)
    hits = []
    if idx.stats(con)["chunks"]:
        notes: list[str] = []
        try:
            hits = srch.search(con, question, args.mode, args.limit, kind=args.kind, source=args.source,
                               notes=notes)
        except embedmod.EmbedError as exc:
            notes.append(srch.fallback_note(exc))
            hits = srch.search(con, question, "keyword", args.limit, kind=args.kind, source=args.source)
        for n in notes:
            _say(f"warning: {n}")
    else:
        _say("index is empty — answering without corpus passages (run `mdbx index`)")
    try:
        result, sources = providers.ask(question, hits, provider=args.provider, model=args.model,
                                        timeout=args.timeout, allow_apple=not args.no_apple)
    except ai_auth.NotConfigured as exc:
        _say(str(exc))
        _say("configure a provider with `mdbx auth set-key <provider>` or `mdbx auth login <provider>`")
        return 1
    except ai_auth.AIAuthError as exc:
        _say(f"error: {exc}")
        return 1
    if args.json:
        print(json.dumps({"question": question, "answer": result.text, "provider": result.provider,
                          "kind": result.kind, "model": result.model, "sources": sources}, indent=2))
        return 0
    print(result.text.rstrip())
    if sources:
        print("\nSources:")
        for s in sources:
            print(f"  [{s['n']}] {s['source']} · {s['heading']}  ({s['location']})")
    _say(f"[{result.provider} · {result.kind} · {result.model}]")
    return 0


def cmd_glean(args) -> int:
    from . import providers

    if not providers.available():
        _say(providers.INSTALL_HINT)
        return 2
    import ai_auth

    try:
        out = providers.glean_search(" ".join(args.query), page_size=args.limit, datasources=args.datasource)
    except ai_auth.NotConfigured as exc:
        _say(str(exc))
        _say("Glean CLI fallback: brew install gleanwork/tap/glean-cli && mdbx auth login glean --mode cli")
        return 1
    except ai_auth.AIAuthError as exc:
        _say(f"error: {exc}")
        return 1
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    if not out["results"]:
        _say("no results")
        return 1
    for i, r in enumerate(out["results"], 1):
        print(f"{i:>2}. {r['title']}  [{r['datasource']}]")
        print(f"    {r['url']}")
        if r["snippet"]:
            print(f"    {r['snippet'][:240]}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mdbx", description=__doc__)
    p.add_argument("--version", action="version", version=f"mdbx {__version__}")
    p.add_argument("--db", type=Path, default=None, help="SQLite index path (env MDBX_DB)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("index", help="build keyword (FTS5) and semantic (Ollama) indexes")
    s.add_argument("--corpus", help="corpus directory (env MDBX_CORPUS)")
    s.add_argument("--skip-keyword", action="store_true")
    s.add_argument("--skip-semantic", action="store_true")
    s.set_defaults(fn=cmd_index)

    s = sub.add_parser("search", aliases=["s"], help="search the corpus")
    s.add_argument("query", nargs="+")
    s.add_argument("-m", "--mode", choices=["hybrid", "keyword", "semantic"], default="hybrid")
    s.add_argument("-n", "--limit", type=int, default=8)
    s.add_argument("-k", "--kind", choices=["skill", "llms", "memory", "recipe"])
    s.add_argument("-s", "--source", help="substring of skill / llms set name")
    s.add_argument("--full", action="store_true", help="print whole chunks")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("show", help="print a corpus file")
    s.add_argument("path")
    s.add_argument("--corpus")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("stats", help="index statistics")
    s.add_argument("--sources", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_stats)

    s = sub.add_parser("recipes", help="list step-by-step recipes (sharding, Private Link, upgrades, ...)")
    s.add_argument("query", nargs="*", help="filter by words in name/title/summary")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_recipes)

    s = sub.add_parser("recipe", help="print one recipe (exact name or unique words)")
    s.add_argument("name", nargs="+")
    s.set_defaults(fn=cmd_recipe)

    s = sub.add_parser("mcp", help="run the MCP server over stdio (needs the mcp extra)")
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("lint", help="lint an MQL file (use - for stdin); exit 1 on errors")
    s.add_argument("file")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("optimize", aliases=["opt"],
                       help="static MQL query optimizer for an MQL file (- for stdin); exit 1 on high/blocking")
    s.add_argument("file")
    s.add_argument("--read-only", action="store_true", help="report findings; do not rewrite")
    s.add_argument("--write", action="store_true", help="write the rewritten queries back to the file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_optimize)

    s = sub.add_parser("export-web", help="write the corpus + search index as static files for the Chrome extension")
    s.add_argument("out", help="output directory (e.g. editors/chrome/data)")
    s.add_argument("--corpus", help="corpus directory (env MDBX_CORPUS)")
    s.add_argument("--no-vectors", action="store_true", help="omit embeddings (keyword search only)")
    s.add_argument("--allow-untracked", action="store_true",
                   help="export a corpus outside git (only when every file in it may be shared)")
    s.set_defaults(fn=cmd_export_web)

    s = sub.add_parser("embed-fetch", help="download the in-process embedding model (~550 MB; needs the onnx extra) "
                                           "so semantic search runs without Ollama")
    s.set_defaults(fn=cmd_embed_fetch)

    s = sub.add_parser("tui", help="interactive MongoDB expertise browser")
    s.set_defaults(fn=cmd_tui)

    s = sub.add_parser("auth", help="AI provider credentials: status | set-key | login | unset | mode | prefer | test "
                       "(Claude, Codex, Antigravity, Glean; needs the ai extra)")
    s.add_argument("rest", nargs=argparse.REMAINDER, help="ai-auth subcommand and flags; default: status")
    s.set_defaults(fn=cmd_auth)

    s = sub.add_parser("ask", help="answer a question from corpus passages with the first available AI provider "
                       "(falls back to on-device Apple Intelligence)")
    s.add_argument("question", nargs="+")
    s.add_argument("-p", "--provider", default="auto", help="claude | codex | antigravity | apple | auto")
    s.add_argument("--model")
    s.add_argument("-m", "--mode", choices=["hybrid", "keyword", "semantic"], default="hybrid")
    s.add_argument("-n", "--limit", type=int, default=6, help="corpus passages to include")
    s.add_argument("-k", "--kind", choices=["skill", "llms", "memory", "recipe"])
    s.add_argument("-s", "--source", help="substring of skill / llms set name")
    s.add_argument("--no-apple", action="store_true", help="do not fall back to Apple Intelligence")
    s.add_argument("--timeout", type=float, default=180)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("glean", help="search Glean (API token → OAuth → glean CLI helper)")
    s.add_argument("query", nargs="+")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.add_argument("-d", "--datasource", action="append", help="e.g. confluence, slack, salesforce")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_glean)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
