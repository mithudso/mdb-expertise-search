"""mcp_server — `mdbx mcp`: expose the corpus search and MQL lint as MCP tools over stdio."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import __version__
from . import embed as embedmod
from . import index as idx
from . import recipes as rec
from . import search as srch
from .mql import operators as ops
from .mql.analyze import analyze
from .mql.optimize import optimize, to_dict

MAX_SHOW_CHARS = 20_000

server = MCPServer(
    "mdbx",
    version=__version__,
    instructions=(
        "Search a curated MongoDB / Atlas expertise corpus (skills + llms docs), lint MQL and "
        "optimize MQL queries (mql_optimize). "
        "Use mdb_search first, then mdb_show with the returned path and line to read context."
    ),
)


def _db():
    return idx.connect(None)


@server.tool()
def mdb_search(
    query: str,
    mode: str = "hybrid",
    limit: int = 8,
    kind: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Search the MongoDB expertise corpus.

    mode: hybrid (keyword + semantic, default), keyword (BM25) or semantic (embeddings).
    kind: skill, llms or memory. source: substring of a skill / llms set name (e.g. "mongodb-expert").
    Returns hits with path, line, heading, source, kind, score and the chunk text.
    """
    if mode not in {"hybrid", "keyword", "semantic"}:
        raise ValueError("mode must be hybrid, keyword or semantic")
    con = _db()
    try:
        try:
            hits = srch.search(con, query, mode, max(1, min(limit, 25)), kind=kind, source=source)
        except embedmod.EmbedError as exc:
            if mode == "semantic":
                raise
            hits = srch.keyword(con, query, max(1, min(limit, 25)), kind=kind, source=source)
            hits and setattr(hits[0], "via", f"keyword (semantic unavailable: {exc})")
        return [
            {"path": h.path, "line": h.line, "heading": h.heading, "source": h.source, "kind": h.kind,
             "score": round(h.score, 4), "via": h.via, "text": h.text}
            for h in hits
        ]
    finally:
        con.close()


@server.tool()
def mdb_show(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read lines of a corpus file (path as returned by mdb_search). Output is capped at 20k characters."""
    root = idx.default_corpus().resolve()
    p = (root / path).resolve()
    if root not in p.parents or not p.is_file():
        raise ValueError(f"not a corpus file: {path}")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(start_line, 1)
    end = end_line if end_line is not None else min(len(lines), start + 199)
    body = "\n".join(lines[start - 1 : end])
    return body[:MAX_SHOW_CHARS]


@server.tool()
def mdb_recipes(topic: str | None = None) -> list[dict]:
    """List step-by-step recipes (shard a collection, add Private Link, upgrade a cluster, restore, ...).

    topic: optional words to filter name/title/summary. Then fetch one with mdb_recipe(name).
    """
    items = rec.load()
    if topic:
        t = topic.lower()
        items = [r for r in items if t in (r.name + " " + r.title + " " + r.summary).lower()]
    return [{"name": r.name, "title": r.title, "summary": r.summary, "applies_to": r.applies_to} for r in items]


@server.tool()
def mdb_recipe(name: str) -> str:
    """Return the full text of one recipe by exact name or unique words (e.g. "shard a collection")."""
    found = rec.find(name)
    if not found:
        raise ValueError(f"no recipe matches {name!r}; call mdb_recipes first")
    if len(found) > 1:
        raise ValueError("ambiguous: " + ", ".join(r.name for r in found))
    return found[0].text


@server.tool()
def mdb_stats() -> dict:
    """Index statistics: chunk counts by kind, number of sources, vectors, embedding model."""
    con = _db()
    try:
        return idx.stats(con)
    finally:
        con.close()


@server.tool()
def mql_lint(text: str) -> list[dict]:
    """Lint MQL (mongosh-style queries, pipelines, updates). Returns diagnostics with 1-based line/column."""
    res = analyze(text)
    out = []
    for d in res.diagnostics:
        line = text.count("\n", 0, d.start) + 1
        col = d.start - (text.rfind("\n", 0, d.start) + 1) + 1
        out.append({"line": line, "column": col, "severity": d.severity, "code": d.code,
                    "message": d.message, "suggestion": d.fix})
    return out


@server.tool()
def mql_optimize(text: str, apply: bool = True) -> dict:
    """Static MQL query optimizer for MQL (find, aggregate, count, updates, watch).

    text may also be slow-query log lines (JSON, one or more), profiler entries, command documents
    ({ find: ..., filter: ... }) or a bare filter / pipeline; `input` in the result says how it was read,
    and log measurements become P9 evidence findings (COLLSCAN, docsExamined vs nreturned, spills, ...).
    Returns findings (severity blocking/high/medium/low, optimizer pass P2-P9, corpus `ref` to read with
    mdb_show), ESR-ordered index recommendations (recommend-only), and, when apply is true, the text
    with result-preserving rewrites applied (same-field $or -> $in, degenerate range -> equality,
    $match hoisting, countDocuments({}) -> estimatedDocumentCount). Confirm with explain() on a cluster.
    """
    return to_dict(optimize(text, apply=apply))


@server.tool()
def mql_operator(name: str) -> dict:
    """Look up an MQL operator ($match, $lookup, $inc, ...): categories, argument kind and description."""
    key = name if name.startswith("$") else "$" + name
    op = ops.get(key)
    if op is None:
        return {"found": False, "suggestions": ops.suggest(key)}
    return {"found": True, "name": op.name, "categories": sorted(op.cats), "argument": op.arg, "doc": op.doc}


def run() -> None:
    server.run(transport="stdio")


