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
Integer evidence outside JavaScript's safe integer range uses exact decimal strings in both ports.
Nonfinite measurements are omitted. Decimal-string evidence does not participate in ratio arithmetic.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from .parser import Node, parse

_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_DOUBLE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_META = {"$db", "lsid", "$clusterTime"}
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
    statements, errors = parse(text)
    if any(_db_call(st.node) for st in statements):
        return Normalized(text, "mongosh", [])
    queries: list[Query] = []
    unknown = bool(errors)
    for st in statements:
        node = st.node
        if node.kind not in {"object", "array"}:
            unknown = True
            continue
        if any(error.start < node.end and node.start < error.end for error in errors):
            return Normalized(text, "mongosh", [])
        if node.kind == "object":
            q = _from_object(text, node)
        elif node.kind == "array" and all(
                i.kind == "object" and len(i.props) == 1 and i.props[0].key.startswith("$") for i in node.items):
            q = [Query(f"db.{PLACEHOLDER}.aggregate({_lit(text, node)})", "pipeline", None)]
        else:
            q = None
        if q is None:
            return Normalized(text, "mongosh", [])
        queries.extend(q)
    # Slow-log excerpts can have a timestamp/header before the structured records. Do not discard
    # unknown statements from command or bare-query input, where they may be executable code.
    if not queries or (unknown and any(q.kind not in {"log", "profile"} for q in queries)):
        return Normalized(text, "mongosh", [])
    return Normalized("\n".join(q.text for q in queries) + "\n", queries[0].kind, queries)


def _db_call(node: Node) -> bool:
    """Recognize actual call syntax, without scanning string or comment contents."""
    if node.kind != "call":
        return False
    while node.target is not None and node.kind in {"call", "member"}:
        node = node.target
    return node.kind == "ident" and node.value == "db"


def _props(node: Node | None) -> dict[str, Node]:
    if node is None or node.kind != "object":
        return {}
    return {p.key: p.value for p in node.props if p.value is not None}


def _from_object(text: str, node: Node) -> list[Query] | None:
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
            coll = ns.split(".", 1)[1]
            s = _write_call(text, _coll_ref(coll), c, "update" if op == "update" else "delete")
            return [Query(s, "profile", coll, ev)] if s is not None else None
        return _from_command(text, cmd, ns, "profile", ev)
    if any(v in top and top[v].kind == "string" for v in _VERBS):
        return _from_command(text, node, None, "command", {})
    return [Query(f"db.{PLACEHOLDER}.find({_lit(text, node)})", "filter", None)]


def _evidence(src: dict[str, Node], cmd: dict[str, Node]) -> dict:
    ev: dict = {}
    for k in EVIDENCE_KEYS:
        if k in src:
            v = _evidence_scalar(src[k])
            if v is not None:
                ev[k] = v
    if "durationMillis" not in ev and "millis" in src and _evidence_scalar(src["millis"]) is not None:
        ev["durationMillis"] = _evidence_scalar(src["millis"])
    if "maxTimeMS" in cmd and _evidence_scalar(cmd["maxTimeMS"]) is not None:
        ev["maxTimeMS"] = _evidence_scalar(cmd["maxTimeMS"])
    return ev


def _evidence_scalar(node: Node):
    value = _scalar(node)
    # JSON numbers have only JavaScript's safe integer range in the browser port. Preserve larger
    # exact integers as decimal strings in both APIs; they are not used for ratio arithmetic.
    return str(value) if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1 else value


def _scalar(n: Node):
    if n.kind == "number":
        v = n.value
        try:
            if isinstance(v, bool) or not math.isfinite(v):
                return None
        except (TypeError, OverflowError):
            return None
        return int(v) if isinstance(v, float) and v.is_integer() else v
    if n.kind in {"string", "bool"}:
        return n.value
    if n.kind == "object":  # {"$numberLong": "123"}
        p = _props(n)
        if len(p) == 1:
            k, value = next(iter(p.items()))
            if value.kind == "string":
                return _numeric_wrapper(k, str(value.value))
    return None


def _numeric_wrapper(key: str, raw: str):
    if key in {"$numberLong", "$numberInt"}:
        # Bound before int() so malformed oversized strings cannot consume arbitrary work.
        if len(raw) > 20 or not _INTEGER.fullmatch(raw):
            return None
        value = int(raw)
        bits = 64 if key == "$numberLong" else 32
        return value if -(1 << (bits - 1)) <= value < (1 << (bits - 1)) else None
    if key == "$numberDouble" and _DOUBLE.fullmatch(raw):
        try:
            value = float(raw)
            return value if math.isfinite(value) else None
        except (ValueError, OverflowError):
            return None
    return None


def _str(n: Node | None) -> str | None:
    return str(n.value) if n is not None and n.kind == "string" else None


def _coll_ref(name: str) -> str:
    # Property syntax can collide with database methods and inherited object properties.
    return f"db.getCollection({json.dumps(name)})"


def _options(text: str, c: dict[str, Node], keys: tuple[str, ...]) -> str:
    body = ", ".join(f"{key}: {_lit(text, c[key])}" for key in keys if key in c)
    return f", {{{body}}}" if body else ""


def _write_call(text: str, db: str, c: dict[str, Node], verb: str, shared: dict[str, Node] | None = None) -> str | None:
    option_keys = ("upsert", "arrayFilters", "collation", "hint", "let", "writeConcern", "bypassDocumentValidation", "comment") \
        if verb == "update" else ("collation", "hint", "let", "writeConcern", "comment")
    fields = {"q", "u", "multi"} if verb == "update" else {"q", "limit"}
    if set(c) - (fields | set(option_keys)) or "q" not in c:
        return None
    options = dict(shared or {})
    options.update({key: c[key] for key in option_keys if key in c})
    args = _lit(text, c["q"])
    if verb == "update":
        if "u" not in c or ("multi" in c and c["multi"].kind != "bool"):
            return None
        update = c["u"]
        replacement = update.kind == "object" and not any(p.key.startswith("$") for p in update.props)
        if update.kind not in {"object", "array"}:
            return None
        multi = "multi" in c and c["multi"].value is True
        if replacement and multi:
            return None
        method = "replaceOne" if replacement else "updateMany" if multi else "updateOne"
        args += ", " + _lit(text, update)
    else:
        limit = _scalar(c["limit"]) if "limit" in c else None
        if isinstance(limit, bool) or limit not in (0, 1):
            return None
        method = "deleteOne" if limit == 1 else "deleteMany"
    return f"{db}.{method}({args}{_options(text, options, option_keys)})"


def _from_command(text: str, cmd: Node | None, ns: str | None, kind: str, ev: dict) -> list[Query] | None:
    c = _props(cmd)
    verb = next((v for v in _VERBS if v in c and c[v].kind == "string"), None)
    coll = str(c[verb].value) if verb else None
    if coll is None and ns and "." in ns:
        coll = ns.split(".", 1)[1]
    if verb is None or coll is None:
        return None
    db = _coll_ref(coll)
    lit = lambda key, default="{}": _lit(text, c[key]) if key in c else default
    allowed = {
        "find": {"filter", "projection", "sort", "skip", "limit", "hint", "batchSize", "collation", "maxTimeMS", "comment", "min", "max", "returnKey", "showRecordId", "allowDiskUse"},
        "aggregate": {"pipeline", "cursor", "allowDiskUse", "maxTimeMS", "collation", "hint", "let", "comment", "readConcern", "writeConcern", "bypassDocumentValidation"},
        "count": {"query", "skip", "limit", "hint", "collation", "maxTimeMS", "comment", "readConcern"},
        "distinct": {"key", "query", "collation", "maxTimeMS", "comment", "readConcern"},
        "update": {"updates", "let", "writeConcern", "bypassDocumentValidation", "comment"},
        "delete": {"deletes", "let", "writeConcern", "comment"},
        "findAndModify": {"query", "sort", "remove", "update", "new", "fields", "upsert", "collation", "arrayFilters", "hint", "let", "maxTimeMS", "writeConcern", "bypassDocumentValidation", "comment"},
    }
    canonical = "findAndModify" if verb == "findandmodify" else verb
    if set(c) - (_META | {verb} | allowed[canonical]):
        return None  # retain the complete source when conversion cannot preserve an option
    if verb == "find":
        args = lit("filter") + (f", {lit('projection')}" if "projection" in c else "")
        s = f"{db}.find({args})"
        for key, meth in (("sort", "sort"), ("skip", "skip"), ("limit", "limit"), ("hint", "hint"),
                          ("batchSize", "batchSize"), ("collation", "collation"), ("maxTimeMS", "maxTimeMS"),
                          ("comment", "comment"), ("min", "min"), ("max", "max"), ("returnKey", "returnKey"),
                          ("showRecordId", "showRecordId"), ("allowDiskUse", "allowDiskUse")):
            if key in c:
                s += f".{meth}({lit(key)})"
    elif verb == "aggregate":
        opts = {k: v for k, v in c.items() if k in allowed[verb] - {"pipeline", "cursor"}}
        if "cursor" in c:
            cursor = _props(c["cursor"])
            if c["cursor"].kind != "object" or set(cursor) - {"batchSize"}:
                return None
            opts.update(cursor)
        s = f"{db}.aggregate({lit('pipeline', '[]')}{_options(text, opts, tuple(sorted(opts)))})"
    elif verb == "count":
        s = f"{db}.count({lit('query')}{_options(text, c, ('skip', 'limit', 'hint', 'collation', 'maxTimeMS', 'comment', 'readConcern'))})"
    elif verb == "distinct":
        s = f"{db}.distinct({lit('key', repr(''))}, {lit('query')}{_options(text, c, ('collation', 'maxTimeMS', 'comment', 'readConcern'))})"
    elif verb == "update":
        return _batch(text, c, db, coll, verb, "updates", kind, ev)
    elif verb == "delete":
        return _batch(text, c, db, coll, verb, "deletes", kind, ev)
    else:  # findAndModify
        remove = "remove" in c and c["remove"].kind == "bool" and c["remove"].value
        options = {k: v for k, v in c.items() if k in allowed[canonical] - {"query", "remove", "update", "new", "fields"}}
        if "fields" in c:
            options["projection"] = c["fields"]
        if "new" in c:
            options["returnNewDocument"] = c["new"]
        # Keep the historic sort layout for existing report fixtures.
        suffix = _options(text, options, tuple(options))
        if "sort" in options and len(options) == 1:
            suffix = f", {{ sort: {lit('sort')} }}"
        if remove:
            if "update" in c or "upsert" in c or "new" in c or "arrayFilters" in c:
                return None
            s = f"{db}.findOneAndDelete({lit('query')}{suffix})"
        else:
            update = c.get("update")
            if update is None or update.kind not in {"object", "array"}:
                return None
            replacement = update.kind == "object" and not any(p.key.startswith("$") for p in update.props)
            s = f"{db}.{'findOneAndReplace' if replacement else 'findOneAndUpdate'}({lit('query')}, {lit('update')}{suffix})"
    return [Query(s, kind, coll, ev)]


def _batch(text: str, c: dict[str, Node], db: str, coll: str, verb: str, key: str, kind: str, ev: dict) -> list[Query] | None:
    operations = c.get(key)
    if operations is None or operations.kind != "array" or not operations.items:
        return None
    shared = {k: v for k, v in c.items() if k in {"let", "writeConcern", "bypassDocumentValidation", "comment"}}
    queries = []
    for operation in operations.items:
        if operation.kind != "object":
            return None
        s = _write_call(text, db, _props(operation), verb, shared)
        if s is None:
            return None
        # Batch measurements cannot be attributed to each individual operation.
        queries.append(Query(s, kind, coll, ev if len(operations.items) == 1 else {}))
    return queries


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
    # Keep line terminators when comment markers occur. They can also occur inside regex literals;
    # preserving the layout is safer than guessing whether a slash starts a comment.
    if "//" in s or "/*" in s:
        return s.strip()
    # Collapse newlines and indentation outside strings when no comment boundary can be extended.
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
        elif ch in "\r\n\u2028\u2029":
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
                value = _numeric_wrapper(p.key, str(v.value))
                if value is not None:
                    rep = f"NumberLong({json.dumps(str(v.value))})" if p.key == "$numberLong" else str(v.value)
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
