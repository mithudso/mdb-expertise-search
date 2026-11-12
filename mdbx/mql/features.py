"""features — editor features (hover, completion) computed from an analysis Result.

Features use text offsets and need no LSP machinery. Optional hover enrichment may perform I/O.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from . import operators as ops
from .analyze import METHODS, Result
from .parser import Parser

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
    start: int  # offset where the replaced token begins
    end: int  # offset after the complete replaced token


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
    contracts = {label: op.arg_for(ctx) for label, ctx in [("stage", "pipeline-item"), ("expression", "expr"), ("accumulator", "accexpr"), ("update", "update"), ("text", "text")]
                 if {"stage": "stage", "expression": "expr", "accumulator": "acc", "update": "update", "text": "sub"}[label] in op.cats and (label != "text" or op.name == "$search")}
    argument = f"`{op.arg}`" if len(set(contracts.values())) <= 1 else "; ".join(f"{label}: `{arg}`" for label, arg in contracts.items())
    md = f"**{op.name}** · {categories(op)}\n\n{op.doc}\n\n_Argument:_ {argument}"
    if expertise:
        try:
            rel = expertise(op.name)
        except Exception:  # noqa: BLE001 - optional enrichment cannot suppress built-in docs
            rel = []
        if rel:
            md += "\n\n**Related expertise** (mdbx)\n" + "\n".join(f"- {r}" for r in rel)
    return md


def _esc(name: str) -> str:
    return name.replace("$", "\\$")


def _snippet(op: ops.Operator, label: str) -> str:
    if op.name == "$count" and label == "accexpr":
        return "{}"
    return _SNIPPET_OVERRIDES.get(op.name) or _VALUE_SNIPPET.get(op.arg_for(label), "$0")


def _op_completion(op: ops.Operator, start: int, end: int, label: str, *, with_value: bool) -> Completion:
    snippet = _snippet(op, label)
    insert = f"{_esc(op.name)}: {snippet}" if with_value else _esc(op.name)
    kind = "stage" if "stage" in op.cats and op.name not in ("$set", "$unset", "$count") else "operator"
    return Completion(op.name, kind, categories(op), op.doc, insert, start, end)


def _candidates(label: str) -> list[ops.Operator]:
    all_ops = list(ops.OPERATORS.values())
    if label == "query":
        return [o for o in all_ops if "qtop" in o.cats]
    if label == "qops":
        return [o for o in all_ops if o.is_a("query") and "qtop" not in o.cats or o.name in {"$options", "$regex"}]
    if label == "expr":
        return [o for o in all_ops if o.is_a("expr", "proj")]
    if label == "accexpr":
        return [o for o in all_ops if o.is_a("acc")]
    if label == "update":
        return [o for o in all_ops if "update" in o.cats]
    if label.startswith("upmods:"):
        return [o for o in all_ops if "mod" in o.cats and (label != "upmods:$addToSet" or o.name == "$each")]
    if label == "update-pipeline":
        return [o for o in all_ops if o.name in ops.UPDATE_PIPELINE_STAGES]
    if label == "pipeline-item":
        return [o for o in all_ops if "stage" in o.cats]
    if label == "sort-meta":
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
    offset = max(0, min(offset, len(text)))
    start = offset
    while start and (text[start - 1].isalnum() or text[start - 1] in "_$"):
        start -= 1
    end = offset
    while end < len(text) and (text[end].isalnum() or text[end] in "_$"):
        end += 1
    prefix = text[start:offset]
    in_regex = any(value.kind == "regex" and value.start < offset < value.end
                   for st in result.statements for value in st.node.walk())
    if in_regex:
        return []
    if prefix.startswith("$$"):
        return [Completion("$$" + n, "variable", "system variable", d, n, start + 2, end)
                for n, d in ops.VARIABLES.items()]
    for st in result.statements:
        for value in st.node.walk():
            if value.kind in {"string", "regex"} and value.start < offset < value.end or (value.kind == "string" and not value.closed and value.start < offset <= value.end):
                return []
    method = False
    for st in result.statements:
        for member in st.node.walk():
            if member.kind != "member" or not member.name_start <= start <= member.end:
                continue
            receiver = member.target
            root = receiver
            while root is not None and root.target is not None:
                root = root.target
            if receiver is not None and receiver.kind in {"member", "call"} and root is not None and root.kind == "ident" and root.value == "db":
                method = True
    if method:
        tail = Parser(text[end:])
        tail.ws()
        called = tail.i < tail.n and tail.s[tail.i] == "("
        return [Completion(n, "method", "collection method", "", n if called else f"{n}($0)",
                           start, end) for n in sorted(METHODS) if n.startswith(prefix)]
    hit = _innermost(result, offset)
    pipeline = None
    for array, context in result.arrays:
        hi = array.end - 1 if array.closed else array.end
        if array.start < offset <= hi and (pipeline is None or array.start > pipeline[0].start):
            pipeline = (array, context)
    if pipeline and (hit is None or pipeline[0].start > hit[0].start):
        label = "update-pipeline" if pipeline[1] == "update-pipeline" else "pipeline-item"
        return [Completion(o.name, "stage", "aggregation stage", o.doc,
                           "{ " + _esc(o.name) + ": " + _snippet(o, label) + " }", start, end)
                for o in _candidates(label)]
    if hit is None:
        return []
    node, label = hit
    key_prop = None
    for index, prop in enumerate(node.props):
        if prop.key_start > offset:
            break
        if prop.key_start <= offset <= prop.key_end:
            key_prop = prop
            break
        value = prop.value
        if value is not None and value.start <= offset <= value.end:
            return []
        if value is None and offset > prop.key_end and (index + 1 == len(node.props) or offset < node.props[index + 1].key_start) and text.find(":", prop.key_end, min(offset, prop.end + 1)) >= 0:
            return []
    if label == "pipeline-item" and any(a.start < node.start < a.end and c == "update-pipeline" for a, c in result.arrays):
        label = "update-pipeline"
    if key_prop is not None:
        start = key_prop.key_start + int(key_prop.quoted)
        end = key_prop.key_end - int(key_prop.quoted and text[key_prop.key_end - 1:key_prop.key_end] in {"'", '"'})
        colon_start = key_prop.key_end
    else:
        colon_start = end
    tail = Parser(text[colon_start:])
    tail.ws()
    with_value = not (tail.i < tail.n and tail.s[tail.i] == ":")
    if key_prop is not None and key_prop.quoted and with_value:
        start, end = key_prop.key_start, key_prop.key_end
    out = [_op_completion(o, start, end, label, with_value=with_value) for o in _candidates(label)]
    for key in _PLAIN_KEYS.get(label, []):
        out.append(Completion(key, "key", f"{label} option", "", f"{key}: $0" if with_value else key, start, end))
    if prefix_is_plain(prefix):
        return [c for c in out if c.kind == "key"] or out
    return out


def prefix_is_plain(prefix: str) -> bool:
    return bool(prefix) and not prefix.startswith("$")
