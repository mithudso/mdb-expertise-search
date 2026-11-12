"""mcp_server — `mdbx mcp`: expose the corpus search and MQL lint as MCP tools over stdio."""
from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
from threading import local

from mcp.server.mcpserver import MCPServer

from . import __version__
from . import embed as embedmod
from . import index as idx
from . import recipes as rec
from . import search as srch
from .mql import operators as ops
from .mql.analyze import analyze
from .mql.optimize import optimize, to_dict
from .safety import read_range

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

_request_state = local()


def _semantic_state():
    path = Path(idx.default_db()).absolute()
    def identity():
        try:
            info = path.stat()
            return str(path), info.st_dev, info.st_ino
        except FileNotFoundError:
            return str(path), None, None
    state = getattr(_request_state, "value", None)
    if state is None or state["identity"] != identity():
        if state is not None:
            state["con"].close()
        con = _db()
        state = {"identity": identity(), "con": con, "store": None}
        _request_state.value = state
    if state["store"] is None:
        state["store"] = srch.VectorStore(state["con"])
    return state



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
    kind: skill, llms, memory or recipe. source: substring of a skill / llms set name (e.g. "mongodb-expert").
    Returns hits with path, line, heading, source, kind, score and the chunk text.
    """
    if mode not in {"hybrid", "keyword", "semantic"}:
        raise ValueError("mode must be hybrid, keyword or semantic")
    state = _semantic_state() if mode != "keyword" else None
    con = state["con"] if state is not None else _db()
    notes: list[str] = []
    try:
        try:
            hits = srch.search(con, query, mode, max(1, min(limit, 25)), kind=kind, source=source, notes=notes,
                               **({"store": state["store"]} if state is not None else {}))
        except embedmod.EmbedError as exc:
            if mode == "semantic":
                raise ValueError(f"{srch.fallback_note(exc)}; start Ollama or use mode=keyword") from None
            notes.append(srch.fallback_note(exc))
            hits = srch.keyword(con, query, max(1, min(limit, 25)), kind=kind, source=source)
        warning = srch.fallback_note(embedmod.EmbedError("semantic backend unavailable")) if notes else None
        if warning and not hits:
            raise ValueError(warning)
        # The fallback is signalled on every hit so an agent cannot miss it: `via` names the reason and
        # `degraded` is set. (Keyword-only mode is not degraded; it is what was asked for.)
        return [
            {"path": h.path, "line": h.line, "heading": h.heading, "source": h.source, "kind": h.kind,
             "score": round(h.score, 4), "via": h.via, "text": h.text,
             **({"degraded": True, "warning": warning} if warning else {})}
            for h in hits
        ]
    finally:
        if state is None:
            con.close()


@server.tool()
def mdb_show(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read lines of a corpus file (path as returned by mdb_search). Output is capped at 20k characters."""
    root = idx.default_corpus().resolve()
    end = end_line if end_line is not None else start_line + 199
    return read_range(root, path, start_line, end, max_chars=MAX_SHOW_CHARS)


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
    starts = [0] + [i + 1 for i, char in enumerate(text) if char == "\n"]
    for d in res.diagnostics:
        line = bisect_right(starts, d.start)
        col = d.start - starts[line - 1] + 1
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
    with supported result-preserving rewrites applied (same-field $or -> $in and dependency-safe
    $match hoisting). Equal-range and approximate-count alternatives remain advisory because their
    semantics can differ. Confirm with explain() on a cluster.
    """
    return to_dict(optimize(text, apply=apply))


@server.tool()
def mql_operator(name: str) -> dict:
    """Look up an MQL operator ($match, $lookup, $inc, ...): categories, argument kind and description."""
    key = name if name.startswith("$") else "$" + name
    op = ops.get(key)
    if op is None:
        return {"found": False, "suggestions": ops.suggest(key)}
    contracts = {context: op.arg_for(label) for context, label in [("query", "query"), ("proj", "projection"), ("stage", "pipeline-item"), ("expr", "expr"), ("acc", "accexpr"), ("update", "update")] if context in op.cats}
    if op.name == "$search":
        contracts["text"] = op.arg_for("text")
    return {"found": True, "name": op.name, "categories": sorted(op.cats),
            "argument": op.arg if len(set(contracts.values())) <= 1 else None,
            "arguments": contracts, "doc": op.doc}


def run() -> None:
    server.run(transport="stdio")


