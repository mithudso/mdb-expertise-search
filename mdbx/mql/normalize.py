"""normalize — turn what people paste from a case into mongosh calls the optimizer can audit.

Accepted input, in the order it is recognised:

* mongosh calls (``db.orders.find({...}).sort({...})``) — returned unchanged;
* mongod/mongos slow-query log lines (JSON with ``attr.command``; ``getMore`` uses
  ``attr.originatingCommand``), one or more per paste;
* profiler documents (``system.profile`` entries with ``op``/``ns``/``command``);
* raw command documents (``{ find: "orders", filter: {...}, sort: {...} }``, ``aggregate``, ``count``,
  ``distinct``, ``update``, ``delete``, ``findAndModify``);
* a bare filter (``{ status: "A" }``) or a bare pipeline (``[{ $match: ... }]``) — audited against a
  placeholder collection named ``collection``.

Values are copied from the source text, so relaxed JSON and mongosh literals survive. Extended-JSON
wrappers (``{"$date": ...}``, ``{"$oid": ...}``, ``{"$numberLong": ...}``) become mongosh literals.
Log and profiler measurements are kept as ``evidence`` for the optimizer's P9 findings.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .parser import Node, parse

#: db.coll.method(  |  db["coll"].method(  |  db.getCollection(
_MONGOSH_CALL = re.compile(
    r"\bdb\s*(?:(?:\.\s*[A-Za-z_$][\w$]*|\[[^\]]*\])\s*\.\s*[A-Za-z_$][\w$]*\s*\(|\.\s*getCollection\s*\()")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*\Z")
_VERBS = ("find", "aggregate", "count", "distinct", "update", "delete", "findAndModify", "findandmodify")
#: measurements copied from a log line / profiler entry (profiler `millis` is renamed durationMillis)
EVIDENCE_KEYS = ("planSummary", "keysExamined", "docsExamined", "nreturned", "durationMillis", "hasSortStage",
                 "usedDisk", "replanned", "replanReason", "fromMultiPlanner", "queryFramework",
                 "planCacheShapeHash", "queryShapeHash", "queryHash", "planCacheKey")
PLACEHOLDER = "collection"


@dataclass
class Query:
    text: str  # one mongosh call
    kind: str  # mongosh | log | profile | command | filter | pipeline
    collection: str | None = None
    evidence: dict = field(default_factory=dict)


@dataclass
class Normalized:
    text: str  # the mongosh text to audit (queries joined by newlines)
    kind: str  # mongosh, or the kind of the first query
    queries: list[Query]

    @property
    def changed(self) -> bool:
        return self.kind != "mongosh"


def normalize(text: str) -> Normalized:
    if _MONGOSH_CALL.search(text):
        return Normalized(text, "mongosh", [])
    statements, _ = parse(text)
    queries: list[Query] = []
    for st in statements:
        node = st.node
        if node.kind == "object":
            q = _from_object(text, node)
        elif node.kind == "array" and node.items and all(
                i.kind == "object" and len(i.props) == 1 and i.props[0].key.startswith("$") for i in node.items):
            q = Query(f"db.{PLACEHOLDER}.aggregate({_lit(text, node)})", "pipeline", None)
        else:
            q = None
        if q is not None:
            queries.append(q)
    if not queries:
        return Normalized(text, "mongosh", [])
    return Normalized("\n".join(q.text for q in queries) + "\n", queries[0].kind, queries)


def _props(node: Node | None) -> dict[str, Node]:
    if node is None or node.kind != "object":
        return {}
    return {p.key: p.value for p in node.props if p.value is not None}


def _from_object(text: str, node: Node) -> Query | None:
    top = _props(node)
    attr = _props(top.get("attr"))
    if attr and ("command" in attr or "originatingCommand" in attr):  # structured log line
        cmd = attr.get("command")
        if "originatingCommand" in attr and (cmd is None or "getMore" in _props(cmd)):
            cmd = attr["originatingCommand"]
        ev = _evidence(attr, _props(cmd))
        return _from_command(text, cmd, _str(attr.get("ns")), "log", ev)
    if "op" in top and "ns" in top and ("command" in top or "originatingCommand" in top):  # profiler entry
        cmd = top.get("command")
        if "originatingCommand" in top and (cmd is None or "getMore" in _props(cmd)):
            cmd = top["originatingCommand"]
        ev = _evidence(top, _props(cmd))
        ns = _str(top.get("ns"))
        c = _props(cmd)
        op = _str(top.get("op"))
        if op in {"update", "remove", "delete"} and "q" in c and ns and "." in ns:
            # profiler write entries hold one statement ({q, u, multi} / {q, limit}), not a command
            db = _coll_ref(ns.split(".", 1)[1])
            if op == "update":
                multi = "multi" in c and c["multi"].kind == "bool" and c["multi"].value
                upd = _lit(text, c["u"]) if "u" in c else "{}"
                s = f"{db}.{'updateMany' if multi else 'updateOne'}({_lit(text, c['q'])}, {upd})"
            else:
                one = "limit" in c and c["limit"].kind == "number" and c["limit"].value == 1
                s = f"{db}.{'deleteOne' if one else 'deleteMany'}({_lit(text, c['q'])})"
            return Query(s, "profile", ns.split(".", 1)[1], ev)
        return _from_command(text, cmd, ns, "profile", ev)
    if any(v in top and top[v].kind == "string" for v in _VERBS):
        return _from_command(text, node, None, "command", {})
    if node.props:  # a bare filter document
        return Query(f"db.{PLACEHOLDER}.find({_lit(text, node)})", "filter", None)
    return None


def _evidence(src: dict[str, Node], cmd: dict[str, Node]) -> dict:
    ev: dict = {}
    for k in EVIDENCE_KEYS:
        if k in src:
            v = _scalar(src[k])
            if v is not None:
                ev[k] = v
    if "durationMillis" not in ev and "millis" in src and _scalar(src["millis"]) is not None:
        ev["durationMillis"] = _scalar(src["millis"])
    if "maxTimeMS" in cmd and _scalar(cmd["maxTimeMS"]) is not None:
        ev["maxTimeMS"] = _scalar(cmd["maxTimeMS"])
    return ev


def _scalar(n: Node):
    if n.kind == "number":
        v = n.value
        return int(v) if isinstance(v, float) and v.is_integer() else v
    if n.kind in {"string", "bool"}:
        return n.value
    if n.kind == "object":  # {"$numberLong": "123"}
        p = _props(n)
        for k in ("$numberLong", "$numberInt", "$numberDouble"):
            if k in p and p[k].kind == "string":
                try:
                    f = float(str(p[k].value))
                    return int(f) if f.is_integer() else f
                except ValueError:
                    return None
    return None


def _str(n: Node | None) -> str | None:
    return str(n.value) if n is not None and n.kind == "string" else None


def _coll_ref(name: str) -> str:
    return f"db.{name}" if _IDENT.match(name) else f"db.getCollection({json.dumps(name)})"


def _from_command(text: str, cmd: Node | None, ns: str | None, kind: str, ev: dict) -> Query | None:
    c = _props(cmd)
    verb = next((v for v in _VERBS if v in c and c[v].kind == "string"), None)
    coll = str(c[verb].value) if verb else None
    if coll is None and ns and "." in ns:
        coll = ns.split(".", 1)[1]
    if verb is None or coll is None:
        return None
    db = _coll_ref(coll)
    lit = lambda key, default="{}": _lit(text, c[key]) if key in c else default
    if verb == "find":
        args = lit("filter") + (f", {lit('projection')}" if "projection" in c else "")
        s = f"{db}.find({args})"
        for key, meth in (("sort", "sort"), ("skip", "skip"), ("limit", "limit"), ("hint", "hint"),
                          ("batchSize", "batchSize")):
            if key in c:
                s += f".{meth}({lit(key)})"
    elif verb == "aggregate":
        s = f"{db}.aggregate({lit('pipeline', '[]')})"
    elif verb == "count":
        s = f"{db}.count({lit('query')})"
    elif verb == "distinct":
        s = f"{db}.distinct({lit('key', repr(''))}, {lit('query')})"
    elif verb == "update":
        first = c["updates"].items[0] if "updates" in c and c["updates"].kind == "array" and c["updates"].items \
            else None
        u = _props(first)
        if "q" not in u:
            return None
        multi = "multi" in u and u["multi"].kind == "bool" and u["multi"].value
        s = f"{db}.{'updateMany' if multi else 'updateOne'}({_lit(text, u['q'])}, " \
            f"{_lit(text, u['u']) if 'u' in u else '{}'})"
    elif verb == "delete":
        first = c["deletes"].items[0] if "deletes" in c and c["deletes"].kind == "array" and c["deletes"].items \
            else None
        d = _props(first)
        if "q" not in d:
            return None
        one = "limit" in d and d["limit"].kind == "number" and d["limit"].value == 1
        s = f"{db}.{'deleteOne' if one else 'deleteMany'}({_lit(text, d['q'])})"
    else:  # findAndModify
        remove = "remove" in c and c["remove"].kind == "bool" and c["remove"].value
        sort = f", {{ sort: {lit('sort')} }}" if "sort" in c else ""
        if remove:
            s = f"{db}.findOneAndDelete({lit('query')}{sort})"
        else:
            s = f"{db}.findOneAndUpdate({lit('query')}, {lit('update')}{sort})"
    return Query(s, kind, coll, ev)


# ---- literal copying with extended-JSON conversion

def _lit(text: str, node: Node) -> str:
    """Source text of ``node`` with extended-JSON wrappers rewritten as mongosh literals, on one line."""
    edits: list[tuple[int, int, str]] = []
    _ejson_edits(text, node, edits)
    out, pos = [], node.start
    for s, e, rep in sorted(edits):
        if s < pos:
            continue  # nested inside an earlier replacement
        out.append(text[pos:s])
        out.append(rep)
        pos = e
    out.append(text[pos:node.end])
    return _one_line("".join(out))


def _one_line(s: str) -> str:
    # collapse newlines (and the indentation after them) outside strings so each query stays on one line
    res, i, quote = [], 0, None
    while i < len(s):
        ch = s[i]
        if quote:
            res.append(ch)
            if ch == "\\" and i + 1 < len(s):
                res.append(s[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
            res.append(ch)
        elif ch in "\r\n":
            while i + 1 < len(s) and s[i + 1] in " \t\r\n":
                i += 1
            if res and res[-1] not in " [{(":
                res.append(" ")
        else:
            res.append(ch)
        i += 1
    return "".join(res).strip()


def _ejson_edits(text: str, node: Node, edits: list[tuple[int, int, str]]) -> None:
    if node.kind == "object" and len(node.props) == 1:
        p = node.props[0]
        v = p.value
        rep = None
        if v is not None:
            vs = text[v.start:v.end]
            if p.key == "$oid" and v.kind == "string":
                rep = f"ObjectId({vs})"
            elif p.key == "$date" and v.kind == "string":
                rep = f"ISODate({vs})"
            elif p.key == "$date" and v.kind == "number":
                rep = f"new Date({vs})"
            elif p.key == "$date" and v.kind == "object":
                inner = _scalar(v)
                rep = f"new Date({inner})" if inner is not None else None
            elif p.key in {"$numberLong", "$numberInt", "$numberDouble"} and v.kind == "string":
                rep = str(v.value)
            elif p.key == "$numberDecimal" and v.kind == "string":
                rep = f"NumberDecimal({vs})"
        if rep is not None:
            edits.append((node.start, node.end, rep))
            return
    for p in node.props:
        if p.value is not None:
            _ejson_edits(text, p.value, edits)
    for it in node.items:
        _ejson_edits(text, it, edits)
