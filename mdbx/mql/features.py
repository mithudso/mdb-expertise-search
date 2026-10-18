"""features — editor features (hover, completion) computed from an analysis Result.

Pure functions over text offsets so they can be unit-tested without any LSP machinery.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from . import operators as ops
from .analyze import METHODS, Result

_WORD = re.compile(r"\$\$?[A-Za-z_]\w*|[A-Za-z_]\w*")

_CAT_LABEL = {
    "stage": "aggregation stage", "query": "query operator", "qtop": "top-level query operator",
    "expr": "aggregation expression", "acc": "accumulator", "update": "update operator",
    "mod": "update modifier", "proj": "projection operator", "sub": "option", "ejson": "Extended JSON",
    "removed": "removed operator",
}
_ORDER = ["stage", "qtop", "query", "expr", "acc", "update", "mod", "proj", "sub", "ejson", "removed"]

_VALUE_SNIPPET = {
    "object": "{ $0 }", "array": "[$0]", "array+": "[$0]", "array2": "[$0]", "string": '"$0"',
    "string|object": '"$0"', "bool": "${1|true,false|}", "any": "$0",
}
_SNIPPET_OVERRIDES = {
    "$group": "{\n  _id: $1,\n  $0\n}",
    "$lookup": '{\n  from: "$1",\n  localField: "$2",\n  foreignField: "$3",\n  as: "$4"\n}',
    "$sort": "{ ${1:field}: ${2|1,-1|} }",
    "$unwind": '"\\$$0"',
    "$limit": "${1:10}",
    "$skip": "${1:0}",
    "$sample": "{ size: ${1:10} }",
    "$count": '"${1:total}"',
    "$cond": "{ if: $1, then: $2, else: $3 }",
    "$regex": '/$0/',
}
_GEO_SUBS = {"$geometry", "$maxDistance", "$minDistance", "$box", "$polygon", "$center", "$centerSphere"}
_TEXT_SUBS = {"$search", "$language", "$caseSensitive", "$diacriticSensitive"}
_PLAIN_KEYS = {
    "lookup": ["from", "localField", "foreignField", "as", "let", "pipeline"],
    "group": ["_id"],
}


@dataclass
class Completion:
    label: str
    kind: str  # operator | stage | variable | method | key | snippet
    detail: str
    doc: str
    insert: str  # LSP snippet syntax
    start: int  # offset where the replaced prefix begins


def word_at(text: str, offset: int) -> tuple[str, int, int] | None:
    for m in _WORD.finditer(text):
        if m.start() <= offset <= m.end():
            return m.group(), m.start(), m.end()
    return None


def categories(op: ops.Operator) -> str:
    return ", ".join(_CAT_LABEL[c] for c in _ORDER if c in op.cats)


def hover_markdown(word: str, expertise: Callable[[str], list[str]] | None = None) -> str | None:
    if word.startswith("$$"):
        doc = ops.VARIABLES.get(word[2:])
        return f"**{word}** · system variable\n\n{doc}" if doc else None
    op = ops.get(word)
    if op is None:
        return None
    md = f"**{op.name}** · {categories(op)}\n\n{op.doc}\n\n_Argument:_ `{op.arg}`"
    if expertise:
        rel = expertise(op.name)
        if rel:
            md += "\n\n**Related expertise** (mdbx)\n" + "\n".join(f"- {r}" for r in rel)
    return md


def _esc(name: str) -> str:
    return name.replace("$", "\\$")


def _op_completion(op: ops.Operator, start: int, *, with_value: bool) -> Completion:
    snippet = _SNIPPET_OVERRIDES.get(op.name) or _VALUE_SNIPPET.get(op.arg, "$0")
    insert = f"{_esc(op.name)}: {snippet}" if with_value else _esc(op.name)
    kind = "stage" if "stage" in op.cats and op.name not in ("$set", "$unset", "$count") else "operator"
    return Completion(op.name, kind, categories(op), op.doc, insert, start)


def _candidates(label: str) -> list[ops.Operator]:
    all_ops = list(ops.OPERATORS.values())
    if label == "query":
        return [o for o in all_ops if "qtop" in o.cats]
    if label == "qops":
        return [o for o in all_ops if o.is_a("query") and "qtop" not in o.cats or o.name in {"$options", "$regex"}]
    if label in {"expr", "accexpr"}:
        return [o for o in all_ops if o.is_a("expr", "acc") or o.name in {"$elemMatch", "$meta", "$slice"}]
    if label == "update":
        return [o for o in all_ops if "update" in o.cats]
    if label == "upmods":
        return [o for o in all_ops if "mod" in o.cats]
    if label == "pipeline-item":
        return [o for o in all_ops if "stage" in o.cats]
    if label == "sort":
        return [ops.OPERATORS["$meta"]]
    if label == "geo":
        return [o for o in all_ops if o.name in _GEO_SUBS]
    if label == "text":
        return [o for o in all_ops if o.name in _TEXT_SUBS]
    return []


def _innermost(result: Result, offset: int):
    best = None
    for node, label in result.objects:
        hi = node.end - 1 if node.closed else node.end
        if node.start < offset <= hi and (best is None or node.start >= best[0].start):
            best = (node, label)
    return best


def completions(result: Result, offset: int) -> list[Completion]:
    text = result.text
    before = text[:offset]
    m = re.search(r"\$\$\w*$", before)
    if m:
        return [Completion(f"$${n}", "variable", "system variable", d, n, m.start() + 2)
                for n, d in ops.VARIABLES.items()]
    m = re.search(r"\b(?:db|[A-Za-z_]\w*)(?:\.[A-Za-z_][\w-]*)+\.([A-Za-z]*)$", before)
    if m and not re.search(r"[\{\[:,]\s*[\w$.]*$", before[: m.start()] + " "):
        return [Completion(n, "method", "collection method", "", f"{n}($0)", m.start(1)) for n in sorted(METHODS)
                if n.startswith(m.group(1))]
    pm = re.search(r"[\$\w]*$", before)
    start = pm.start() if pm else offset
    hit = _innermost(result, offset)
    if hit is None:
        for arr, _ in result.arrays:
            hi = arr.end - 1 if arr.closed else arr.end
            if arr.start < offset <= hi:
                return [Completion(o.name, "stage", "aggregation stage", o.doc,
                                   "{ " + _esc(o.name) + ": " + (_SNIPPET_OVERRIDES.get(o.name) or _VALUE_SNIPPET.get(o.arg, "$0")) + " }",
                                   start)
                        for o in _candidates("pipeline-item")]
        return []
    node, label = hit
    for p in node.props:
        v = p.value
        if v is not None and v.start <= offset <= v.end:
            return []  # cursor is inside a value, not a key
        if v is None and ":" in text[p.key_end:offset] and offset > p.key_end:
            return []
    after = text[offset: offset + 40].lstrip(" \t")
    with_value = not after.startswith(":")
    out = [_op_completion(o, start, with_value=with_value) for o in _candidates(label)]
    for key in _PLAIN_KEYS.get(label, []):
        out.append(Completion(key, "key", f"{label} option", "", f"{key}: $0" if with_value else key, start))
    if prefix_is_plain(before[start:]):
        return [c for c in out if c.kind == "key"] or out
    return out


def prefix_is_plain(prefix: str) -> bool:
    return bool(prefix) and not prefix.startswith("$")
