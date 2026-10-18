"""analyze — context-aware checks over the MQL tree.

The analyzer assigns every object it understands a *context label* (query, qops, expr, fields,
group, update, upmods, pipeline-item, ...). Diagnostics come from validating keys and arguments
against that context; completion later reuses the same labels to decide which operators fit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import operators as ops
from .parser import Node, ParseError, Prop, Statement, parse

ERROR, WARNING, INFO, HINT = "error", "warning", "info", "hint"

#: method name -> context of each positional argument ("-" = not analysed)
METHODS: dict[str, list[str]] = {
    "find": ["query", "proj"], "findOne": ["query", "proj"], "countDocuments": ["query"],
    "count": ["query"], "distinct": ["-", "query"], "deleteOne": ["query"], "deleteMany": ["query"],
    "remove": ["query"], "findOneAndDelete": ["query"],
    "findOneAndUpdate": ["query", "update"], "updateOne": ["query", "update"],
    "updateMany": ["query", "update"], "update": ["query", "update"],
    "findOneAndReplace": ["query", "-"], "replaceOne": ["query", "-"],
    "aggregate": ["pipeline"], "watch": ["pipeline"],
    "sort": ["sort"], "project": ["proj"], "projection": ["proj"],
}

_KIND_NAMES = {
    "object": "an object", "array": "an array", "array+": "a non-empty array",
    "array2": "an array of exactly 2 elements", "string": "a string", "bool": "a boolean",
    "int": "an integer", "posint": "a positive integer", "nonneg": "a non-negative integer",
    "number": "a number",
}
_DYNAMIC = {"call", "ident", "member", "error"}


@dataclass
class Diag:
    start: int
    end: int
    severity: str
    code: str
    message: str
    fix: str | None = None  # replacement text for the flagged range


@dataclass
class Symbol:
    name: str
    kind: str  # variable | method | stage
    start: int
    end: int
    children: list[Symbol] = field(default_factory=list)


@dataclass
class Result:
    text: str
    statements: list[Statement]
    diagnostics: list[Diag]
    objects: list[tuple[Node, str]]  # (object node, context label)
    arrays: list[tuple[Node, str]]
    symbols: list[Symbol]


def _num(node: Node | None) -> float | None:
    return float(node.value) if node is not None and node.kind == "number" else None


def _kind_ok(node: Node, kind: str) -> bool:
    if node.kind in _DYNAMIC:
        return True
    for k in kind.split("|"):
        if k == "any":
            return True
        if k == "object" and node.kind == "object":
            return True
        if k == "array" and node.kind == "array":
            return True
        if k == "array+" and node.kind == "array" and node.items:
            return True
        if k == "array2" and node.kind == "array" and len(node.items) == 2:
            return True
        if k == "string" and node.kind == "string":
            return True
        if k == "bool" and node.kind in {"bool", "number"}:
            return True
        if k in {"int", "posint", "nonneg", "number"} and node.kind == "number":
            v = float(node.value)  # type: ignore[arg-type]
            if k == "number":
                return True
            if v != int(v):
                continue
            if k == "posint" and v <= 0:
                continue
            if k == "nonneg" and v < 0:
                continue
            return True
    return False


class Analyzer:
    def __init__(self, text: str):
        self.text = text
        self.statements, perrs = parse(text)
        self.diags: list[Diag] = [self._syntax(e) for e in perrs]
        self.objects: list[tuple[Node, str]] = []
        self.arrays: list[tuple[Node, str]] = []
        self.stage_syms: dict[int, list[Symbol]] = {}
        self.done: set[int] = set()
        self.var_ctx: dict[str, str] = {}
        self.vars: dict[str, Node] = {}

    # ---- reporting
    @staticmethod
    def _syntax(e: ParseError) -> Diag:
        return Diag(e.start, e.end, ERROR, "syntax", e.message)

    def add(self, start: int, end: int, sev: str, code: str, msg: str, fix: str | None = None) -> None:
        self.diags.append(Diag(start, max(end, start + 1), sev, code, msg, fix))

    def on_prop(self, p: Prop, sev: str, code: str, msg: str, fix: str | None = None) -> None:
        self.add(p.key_start, p.key_end, sev, code, msg, fix)

    def unknown(self, p: Prop, want: str = "operator") -> None:
        sug = ops.suggest(p.key)
        if sug:
            self.on_prop(p, ERROR, "unknown-operator", f"Unknown {want} {p.key}. Did you mean {sug[0]}?", sug[0])
        else:
            self.on_prop(p, WARNING, "unknown-operator",
                         f"{p.key} is not in the built-in operator table (it may be newer than this server).")

    def dups(self, obj: Node) -> None:
        seen: dict[str, Prop] = {}
        for p in obj.props:
            if p.key in seen:
                self.on_prop(p, WARNING, "duplicate-key",
                             f"Duplicate key {p.key!r}: the later value silently replaces the earlier one.")
            seen[p.key] = p

    def arg(self, p: Prop, op: ops.Operator, *, strict: bool = True) -> bool:
        """Validate the argument of ``op``. Returns whether it is acceptable."""
        v = p.value
        if v is None or not strict:
            return True
        if _kind_ok(v, op.arg):
            return True
        want = " or ".join(_KIND_NAMES.get(k, k) for k in op.arg.split("|"))
        self.add(v.start, v.end, ERROR, "bad-argument", f"{op.name} expects {want}, got {v.kind}.")
        return False

    # ---- entry
    def run(self) -> Result:
        self.collect_vars()
        for st in self.statements:
            node = st.node
            if st.decl:
                self.vars[st.decl] = node
            ctx = self.var_ctx.get(st.decl or "")
            if ctx and id(node) not in self.done:
                self.value(node, ctx)
            elif id(node) not in self.done:
                self.statement_node(node)
            for c in node.walk():
                if c.kind == "call" and id(c) not in self.done:
                    self.call(c)
        self.diags.sort(key=lambda d: (d.start, d.end))
        return Result(self.text, self.statements, self.diags, self.objects, self.arrays, self.symbols())

    def collect_vars(self) -> None:
        for st in self.statements:
            for c in st.node.walk():
                if c.kind != "call" or c.target is None or c.target.kind != "member":
                    continue
                spec = METHODS.get(str(c.target.value))
                if not spec:
                    continue
                for i, a in enumerate(c.items):
                    if a.kind == "ident" and i < len(spec) and spec[i] != "-":
                        self.var_ctx.setdefault(str(a.value), spec[i])

    def statement_node(self, node: Node) -> None:
        if node.kind in {"array", "object"}:
            self.value(node, "auto")
        elif node.kind == "call":
            self.call(node)

    def call(self, c: Node) -> None:
        self.done.add(id(c))
        if c.target is None or c.target.kind != "member":
            return
        spec = METHODS.get(str(c.target.value))
        if not spec:
            return
        for i, a in enumerate(c.items):
            if i < len(spec) and spec[i] != "-":
                if a.kind == "ident" and str(a.value) in self.vars:
                    continue  # analysed at its declaration with this context
                self.value(a, spec[i])

    # ---- dispatch
    def value(self, node: Node, ctx: str) -> None:
        if id(node) in self.done:
            return
        self.done.add(id(node))
        if ctx == "pipeline":
            self.pipeline(node)
        elif ctx == "query":
            if self.need(node, "object", "a query document"):
                self.query(node)
        elif ctx == "update":
            if node.kind == "array":
                self.pipeline(node, update=True)
            elif self.need(node, "object", "an update document"):
                self.update(node)
        elif ctx == "proj":
            if node.kind == "object":
                self.fields(node, project=True, label="proj")
        elif ctx == "sort":
            if node.kind == "object":
                self.sort(node, strict_strings=False)
        elif ctx == "auto":
            self.auto(node)

    def need(self, node: Node, kind: str, what: str) -> bool:
        if node.kind in _DYNAMIC or node.kind == kind:
            return node.kind == kind
        self.add(node.start, node.end, ERROR, "bad-argument", f"Expected {what}, got {node.kind}.")
        return False

    def auto(self, node: Node) -> None:
        if node.kind == "array":
            if self.looks_like_pipeline(node):
                self.pipeline(node)
            return
        if node.kind != "object" or not node.props:
            return
        keys = [p.key for p in node.props]
        if len(keys) == 1 and keys[0] in ops.STAGES and keys[0] not in ops.UPDATE_OPS:
            self.stage(node, 0, True, False, False, standalone=True)
        elif all(k in ops.UPDATE_OPS or k in ops.OPERATORS and "removed" in ops.OPERATORS[k].cats for k in keys):
            self.update(node, require_ops=False)
        else:
            self.query(node, lenient=True)

    @staticmethod
    def looks_like_pipeline(arr: Node) -> bool:
        return bool(arr.items) and all(
            i.kind == "object" and len(i.props) == 1 and i.props[0].key in ops.STAGES for i in arr.items
        )

    # ---- query documents
    def query(self, obj: Node, *, in_match: bool = False, first: bool = False, lenient: bool = False) -> None:
        self.objects.append((obj, "query"))
        self.dups(obj)
        for p in obj.props:
            v = p.value
            if p.key.startswith("$"):
                op = ops.get(p.key)
                if op is None:
                    self.unknown(p)
                elif "qtop" in op.cats:
                    self.query_top(p, op, in_match=in_match, first=first)
                elif op.is_a("ejson") or lenient and op.is_a("expr", "acc", "stage", "update"):
                    pass
                elif op.is_a("query"):
                    self.on_prop(p, WARNING, "misplaced-operator",
                                 f"{p.key} is a field operator; put it inside a field: {{ field: {{ {p.key}: … }} }}.")
                else:
                    self.on_prop(p, WARNING, "misplaced-operator", f"{p.key} is not a query operator here.")
            elif v is not None and v.kind == "object":
                self.field_value(v)
            elif v is not None and v.kind == "array":
                pass

    def query_top(self, p: Prop, op: ops.Operator, *, in_match: bool, first: bool) -> None:
        v = p.value
        name = p.key
        if name in {"$and", "$or", "$nor"}:
            if v is None:
                return
            if v.kind == "array":
                if not v.items:
                    self.add(v.start, v.end, ERROR, "bad-argument", f"{name} requires a non-empty array.")
                for it in v.items:
                    if it.kind == "object":
                        self.query(it, in_match=in_match, first=first)
                    elif it.kind not in _DYNAMIC:
                        self.add(it.start, it.end, ERROR, "bad-argument", f"Each {name} element must be an object.")
            elif v.kind not in _DYNAMIC:
                self.add(v.start, v.end, ERROR, "bad-argument", f"{name} expects a non-empty array.")
        elif name == "$expr":
            if v is not None:
                self.expr(v)
        elif name == "$text":
            if in_match and not first:
                self.on_prop(p, ERROR, "stage-position", "$text is only allowed in the first stage of a pipeline.")
            if v is not None and v.kind == "object":
                self.objects.append((v, "text"))
                keys = {q.key for q in v.props}
                if "$search" not in keys:
                    self.add(v.start, v.end, ERROR, "missing-field", "$text requires a $search string.")
                for q in v.props:
                    if q.key not in {"$search", "$language", "$caseSensitive", "$diacriticSensitive"}:
                        self.on_prop(q, WARNING, "unknown-operator", f"{q.key} is not a $text option.")
            elif v is not None and v.kind not in _DYNAMIC:
                self.add(v.start, v.end, ERROR, "bad-argument", "$text expects an object with $search.")
        elif name == "$where":
            self.on_prop(p, WARNING, "perf",
                         "$where runs JavaScript per document, cannot use indexes and is an injection risk; "
                         "prefer $expr or regular operators.")
            if in_match:
                self.on_prop(p, ERROR, "misplaced-operator", "$where is not allowed in a $match stage.")
        elif name == "$sampleRate":
            n = _num(v)
            if v is not None and v.kind == "number" and not (0 <= (n or 0) <= 1):
                self.add(v.start, v.end, ERROR, "bad-argument", "$sampleRate must be between 0 and 1.")

    def field_value(self, obj: Node) -> None:
        keys = [p.key for p in obj.props]
        dollar = [k for k in keys if k.startswith("$")]
        if not dollar:
            return  # embedded-document equality
        if all(ops.get(k) and ops.OPERATORS[k].is_a("ejson") for k in dollar) and len(dollar) == len(keys):
            return  # Extended JSON value such as { $oid: "…" }
        plain = [p for p in obj.props if not p.key.startswith("$")]
        for p in plain:
            self.on_prop(p, ERROR, "mixed-keys",
                         f"{p.key!r} is a field name inside an operator expression; "
                         "operators and field names cannot be mixed.")
        self.qops(obj)

    def qops(self, obj: Node) -> None:
        self.objects.append((obj, "qops"))
        self.dups(obj)
        keys = {p.key for p in obj.props}
        for p in obj.props:
            if not p.key.startswith("$"):
                continue
            op = ops.get(p.key)
            v = p.value
            if op is None:
                self.unknown(p)
                continue
            if op.is_a("ejson"):
                continue
            if "qtop" in op.cats and not op.is_a("query", "sub"):
                self.on_prop(p, ERROR, "misplaced-operator",
                             f"{p.key} must be at the top level of the query, not inside a field.")
                continue
            if not op.is_a("query", "sub", "proj"):
                self.on_prop(p, WARNING, "misplaced-operator", f"{p.key} is not a field query operator.")
                continue
            name = p.key
            if name in {"$in", "$nin", "$all"}:
                self.arg(p, ops.Operator(name, op.cats, "array", op.doc))
            elif name == "$not":
                if v is not None and v.kind == "object":
                    self.qops(v)
                elif v is not None and v.kind not in {"regex", *_DYNAMIC}:
                    self.add(v.start, v.end, ERROR, "bad-argument", "$not expects an operator expression or a regex.")
            elif name == "$elemMatch":
                if v is not None and v.kind == "object":
                    inner = [q.key for q in v.props]
                    if inner and all(k in ops.OPERATORS and ops.OPERATORS[k].is_a("query", "sub") and
                                     "qtop" not in ops.OPERATORS[k].cats for k in inner):
                        self.qops(v)
                    else:
                        self.query(v)
                elif v is not None and v.kind not in _DYNAMIC:
                    self.add(v.start, v.end, ERROR, "bad-argument", "$elemMatch expects an object.")
            elif name == "$regex":
                if v is not None and v.kind not in {"string", "regex", *_DYNAMIC}:
                    self.add(v.start, v.end, ERROR, "bad-argument", "$regex expects a string or regex.")
            elif name == "$options":
                if "$regex" not in keys:
                    self.on_prop(p, WARNING, "missing-field", "$options has no effect without a $regex sibling.")
                self.arg(p, op)
            elif name == "$type":
                if v is not None and v.kind not in {"string", "number", "array", *_DYNAMIC}:
                    self.add(v.start, v.end, ERROR, "bad-argument", "$type expects a type name, number or array.")
            elif name in {"$near", "$nearSphere", "$geoWithin", "$geoIntersects"}:
                if v is not None and v.kind == "object":
                    self.objects.append((v, "geo"))
            else:
                self.arg(p, op)

    # ---- aggregation expressions
    def expr(self, node: Node) -> None:
        if node.kind == "array":
            for it in node.items:
                self.expr(it)
        elif node.kind == "object":
            self.expr_object(node)

    def expr_object(self, obj: Node) -> None:
        self.objects.append((obj, "expr"))
        self.dups(obj)
        dollar = [p for p in obj.props if p.key.startswith("$")]
        if not dollar:
            for p in obj.props:
                if p.value is not None:
                    self.expr(p.value)
            return
        if len(obj.props) > 1 and not all(
            ops.get(p.key) and ops.OPERATORS[p.key].is_a("sub", "ejson") for p in obj.props
        ):
            self.add(obj.start, obj.start + 1, ERROR, "stage-shape",
                     "An expression object must contain exactly one operator key; "
                     f"found {len(obj.props)} keys.")
        for p in dollar:
            op = ops.get(p.key)
            if op is None:
                self.unknown(p, "expression operator")
                continue
            if "removed" in op.cats:
                self.on_prop(p, ERROR, "removed-operator", f"{p.key}: {op.doc}")
                continue
            if op.is_a("sub", "ejson"):
                continue
            if not op.is_a("expr", "acc", "proj"):
                self.on_prop(p, WARNING, "misplaced-operator", f"{p.key} is not an aggregation expression operator.")
                continue
            v = p.value
            if p.key in {"$literal", "$function", "$accumulator"} or v is None:
                continue
            if p.key == "$cond" and v.kind == "array" and len(v.items) != 3:
                self.add(v.start, v.end, ERROR, "bad-argument", "$cond array form needs exactly 3 elements [if, then, else].")
            elif op.arg == "array2" and v.kind == "array" and len(v.items) != 2:
                self.add(v.start, v.end, ERROR, "bad-argument", f"{p.key} expects exactly 2 arguments.")
            self.expr(v)

    # ---- projection / $addFields
    def fields(self, obj: Node, *, project: bool, label: str = "fields") -> None:
        self.objects.append((obj, label))
        self.dups(obj)
        flags: list[tuple[Prop, bool]] = []
        self.collect_proj(obj, flags, top=True)
        if project:
            inc = [(p, f) for p, f in flags if f and p.key != "_id"]
            exc = [(p, f) for p, f in flags if not f and p.key != "_id"]
            if inc and exc:
                for p, _ in exc:
                    self.on_prop(p, ERROR, "projection-mix",
                                 "Cannot mix exclusion with inclusion in one projection (only _id may differ).")

    def collect_proj(self, obj: Node, flags: list[tuple[Prop, bool]], *, top: bool) -> None:
        for p in obj.props:
            v = p.value
            if p.key.startswith("$"):
                self.on_prop(p, WARNING, "misplaced-operator",
                             f"Field names here cannot start with '$' ({p.key}); "
                             "operators belong inside a field's value.")
                continue
            if v is None:
                continue
            if v.kind in {"number", "bool"}:
                flags.append((p, bool(v.value)))
            elif v.kind == "object" and not any(q.key.startswith("$") for q in v.props):
                self.objects.append((v, "fields"))
                self.collect_proj(v, flags, top=False)
            else:
                flags.append((p, True))
                self.expr(v)

    # ---- $group / $sort
    def group(self, obj: Node) -> None:
        self.objects.append((obj, "group"))
        self.dups(obj)
        if not any(p.key == "_id" for p in obj.props):
            self.add(obj.start, obj.start + 1, ERROR, "missing-field",
                     "$group requires an _id field (use _id: null to aggregate all documents).")
        for p in obj.props:
            v = p.value
            if v is None:
                continue
            if p.key == "_id":
                self.expr(v)
                continue
            self.accumulator(p)

    def accumulator(self, p: Prop) -> None:
        v = p.value
        assert v is not None
        if v.kind in _DYNAMIC:
            return
        if v.kind != "object" or len(v.props) != 1 or not v.props[0].key.startswith("$"):
            self.on_prop(p, ERROR, "stage-shape",
                         f"Field {p.key!r} must be an accumulator expression such as {{ $sum: 1 }}.")
            return
        self.objects.append((v, "accexpr"))
        a = v.props[0]
        op = ops.get(a.key)
        if op is None:
            self.unknown(a, "accumulator")
        elif not op.is_a("acc", "expr"):
            self.on_prop(a, ERROR, "misplaced-operator", f"{a.key} is not an accumulator.")
        elif a.value is not None and a.key not in {"$accumulator"}:
            self.expr(a.value)

    def sort(self, obj: Node, *, strict_strings: bool) -> None:
        self.objects.append((obj, "sort"))
        self.dups(obj)
        for p in obj.props:
            v = p.value
            if v is None or v.kind in _DYNAMIC:
                continue
            if v.kind == "number" and v.value in (1, -1):
                continue
            if v.kind == "object" and len(v.props) == 1 and v.props[0].key == "$meta":
                continue
            if v.kind == "string" and not strict_strings and v.value in {"asc", "desc", "ascending", "descending"}:
                continue
            self.add(v.start, v.end, ERROR, "bad-argument", f"Sort order for {p.key!r} must be 1, -1 or {{ $meta: … }}.")

    # ---- update documents
    def update(self, obj: Node, *, require_ops: bool = True) -> None:
        self.objects.append((obj, "update"))
        self.dups(obj)
        dollar = [p for p in obj.props if p.key.startswith("$")]
        plain = [p for p in obj.props if not p.key.startswith("$")]
        if dollar and plain:
            for p in plain:
                self.on_prop(p, ERROR, "update-shape",
                             f"{p.key!r} mixes a plain field with update operators; wrap it in $set.")
        elif plain and require_ops:
            self.add(obj.start, obj.start + 1, ERROR, "update-shape",
                     "Update document requires atomic operators such as $set; "
                     "a plain document is only valid for replaceOne/findOneAndReplace.")
        elif not obj.props and require_ops:
            self.add(obj.start, obj.end, ERROR, "update-shape", "Update document is empty; add an operator such as $set.")
        for p in dollar:
            op = ops.get(p.key)
            v = p.value
            if op is None:
                self.unknown(p, "update operator")
                continue
            if "removed" in op.cats:
                self.on_prop(p, ERROR, "removed-operator", f"{p.key}: {op.doc}")
                continue
            if "update" not in op.cats:
                self.on_prop(p, ERROR, "misplaced-operator", f"{p.key} is not an update operator.")
                continue
            if v is None:
                continue
            if v.kind != "object":
                if v.kind not in _DYNAMIC:
                    self.add(v.start, v.end, ERROR, "bad-argument", f"{p.key} expects an object of field: value pairs.")
                continue
            self.dups(v)
            for f in v.props:
                self.update_field(p.key, f)

    def update_field(self, opname: str, f: Prop) -> None:
        v = f.value
        if v is None:
            return
        if opname in {"$inc", "$mul"} and v.kind not in {"number", *_DYNAMIC, "object"}:
            self.add(v.start, v.end, ERROR, "bad-argument", f"{opname} requires a numeric value for {f.key!r}.")
        elif opname == "$pop" and not (v.kind in _DYNAMIC or (v.kind == "number" and v.value in (1, -1))):
            self.add(v.start, v.end, ERROR, "bad-argument", "$pop requires 1 (last) or -1 (first).")
        elif opname == "$rename" and v.kind not in {"string", *_DYNAMIC}:
            self.add(v.start, v.end, ERROR, "bad-argument", "$rename requires the new field name as a string.")
        elif opname in {"$push", "$addToSet"} and v.kind == "object" and any(q.key.startswith("$") for q in v.props):
            self.objects.append((v, "upmods"))
            allowed = {"$each", "$slice", "$sort", "$position"} if opname == "$push" else {"$each"}
            for q in v.props:
                if q.key not in allowed:
                    self.on_prop(q, ERROR, "misplaced-operator", f"{q.key} is not a valid modifier for {opname}.")
                elif q.key == "$each" and q.value is not None and q.value.kind not in {"array", *_DYNAMIC}:
                    self.add(q.value.start, q.value.end, ERROR, "bad-argument", "$each expects an array.")
            if not any(q.key == "$each" for q in v.props):
                self.on_prop(v.props[0], ERROR, "missing-field", f"Modifiers on {opname} require $each.")
        elif opname == "$pull" and v.kind == "object" and any(q.key.startswith("$") for q in v.props):
            self.qops(v)

    # ---- pipelines
    def pipeline(self, node: Node, *, update: bool = False, facet: bool = False) -> None:
        if id(node) in self.done and node.kind == "array" and any(a is node for a, _ in self.arrays):
            return
        self.done.add(id(node))
        if node.kind == "object":
            self.add(node.start, node.end, ERROR, "bad-argument", "A pipeline must be an array of stages, not an object.")
            return
        if node.kind != "array":
            return
        self.arrays.append((node, "pipeline"))
        syms: list[Symbol] = []
        n = len(node.items)
        for i, item in enumerate(node.items):
            if item.kind != "object":
                if item.kind not in _DYNAMIC:
                    self.add(item.start, item.end, ERROR, "stage-shape", "Each pipeline stage must be an object.")
                continue
            name = self.stage(item, i, i == n - 1, update, facet)
            if name:
                syms.append(Symbol(name, "stage", item.start, item.end))
        self.stage_syms[id(node)] = syms

    def stage(self, obj: Node, idx: int, last: bool, update: bool, facet: bool, *, standalone: bool = False) -> str | None:
        self.objects.append((obj, "pipeline-item"))
        self.dups(obj)
        if len(obj.props) != 1:
            msg = "Empty stage object." if not obj.props else (
                f"A stage must have exactly one key; found {len(obj.props)} (split into separate stages).")
            self.add(obj.start, obj.start + 1, ERROR, "stage-shape", msg)
            return obj.props[0].key if obj.props else None
        p = obj.props[0]
        op = ops.get(p.key)
        if op is None:
            self.unknown(p, "stage")
            return p.key
        if "stage" not in op.cats:
            hint = ""
            if op.is_a("query", "qtop"):
                hint = f" Did you mean {{ $match: {{ … {p.key} … }} }}?"
            elif op.is_a("expr", "acc"):
                hint = " Expressions go inside $project, $addFields or $group."
            self.on_prop(p, ERROR, "misplaced-operator", f"{p.key} is not an aggregation stage.{hint}")
            return p.key
        if not standalone:
            if p.key in ops.FIRST_STAGE_ONLY and idx > 0:
                self.on_prop(p, ERROR, "stage-position", f"{p.key} must be the first stage of the pipeline.")
            if p.key in ops.LAST_STAGE_ONLY and not last:
                self.on_prop(p, ERROR, "stage-position", f"{p.key} must be the last stage of the pipeline.")
            if facet and p.key in ops.NOT_IN_FACET:
                self.on_prop(p, ERROR, "stage-position", f"{p.key} is not allowed inside $facet.")
            if update and p.key not in ops.UPDATE_PIPELINE_STAGES:
                self.on_prop(p, ERROR, "stage-position",
                             f"{p.key} is not allowed in an update pipeline "
                             "(use $addFields/$set, $project/$unset, $replaceRoot/$replaceWith).")
        self.stage_arg(p, op, idx == 0)
        return p.key

    def stage_arg(self, p: Prop, op: ops.Operator, first: bool) -> None:
        v = p.value
        name = p.key
        if v is None:
            return
        free_form = {"$sortByCount", "$redact", "$replaceWith", "$unionWith", "$out", "$merge", "$unwind", "$unset"}
        if name not in free_form and not self.arg(p, op):
            return
        if name == "$match":
            if v.kind == "object":
                self.query(v, in_match=True, first=first)
                for q in v.props:
                    if q.key in {"$near", "$nearSphere"}:
                        self.on_prop(q, ERROR, "misplaced-operator", f"{q.key} is not allowed in $match; use $geoNear.")
        elif name == "$project":
            if v.kind == "object":
                self.fields(v, project=True)
        elif name in {"$addFields", "$set"}:
            if v.kind == "object":
                self.fields(v, project=False)
        elif name == "$group":
            if v.kind == "object":
                self.group(v)
        elif name == "$sort":
            if v.kind == "object":
                self.sort(v, strict_strings=True)
        elif name == "$unwind":
            if v.kind == "string" and not str(v.value).startswith("$"):
                self.add(v.start, v.end, ERROR, "bad-argument", "$unwind path must start with '$' (e.g. \"$items\").")
            elif v.kind == "object":
                self.objects.append((v, "stage"))
                path = next((q for q in v.props if q.key == "path"), None)
                if path is None:
                    self.add(v.start, v.start + 1, ERROR, "missing-field", "$unwind requires a path.")
                elif path.value is not None and path.value.kind == "string" and not str(path.value.value).startswith("$"):
                    self.add(path.value.start, path.value.end, ERROR, "bad-argument", "$unwind path must start with '$'.")
            elif v.kind not in {"string", *_DYNAMIC}:
                self.add(v.start, v.end, ERROR, "bad-argument", "$unwind expects a path string or an object.")
        elif name == "$lookup":
            if v.kind == "object":
                self.lookup(v)
        elif name == "$facet":
            if v.kind == "object":
                self.objects.append((v, "stage"))
                for q in v.props:
                    if q.value is not None:
                        self.pipeline(q.value, facet=True)
        elif name == "$unionWith":
            if v.kind == "object":
                self.objects.append((v, "stage"))
                for q in v.props:
                    if q.key == "pipeline" and q.value is not None:
                        self.pipeline(q.value)
        elif name in {"$replaceRoot", "$replaceWith"}:
            if name == "$replaceRoot" and v.kind == "object":
                self.objects.append((v, "stage"))
                nr = next((q for q in v.props if q.key == "newRoot"), None)
                if nr is None:
                    self.add(v.start, v.start + 1, ERROR, "missing-field", "$replaceRoot requires newRoot.")
                elif nr.value is not None:
                    self.expr(nr.value)
            elif name == "$replaceWith":
                self.expr(v)
        elif name in {"$sortByCount", "$redact"}:
            self.expr(v)
        elif name == "$unset":
            if v.kind not in {"string", "array", *_DYNAMIC}:
                self.add(v.start, v.end, ERROR, "bad-argument", "$unset expects a field name or an array of names.")
        elif name == "$graphLookup" and v.kind == "object":
            self.objects.append((v, "stage"))
            have = {q.key for q in v.props}
            for need in ("from", "startWith", "connectFromField", "connectToField", "as"):
                if need not in have:
                    self.add(v.start, v.start + 1, ERROR, "missing-field", f"$graphLookup requires {need}.")
            for q in v.props:
                if q.key == "startWith" and q.value is not None:
                    self.expr(q.value)
                elif q.key == "restrictSearchWithMatch" and q.value is not None and q.value.kind == "object":
                    self.query(q.value)
        elif name == "$geoNear" and v.kind == "object":
            self.objects.append((v, "stage"))
            have = {q.key for q in v.props}
            for need in ("near", "distanceField"):
                if need not in have:
                    self.add(v.start, v.start + 1, ERROR, "missing-field", f"$geoNear requires {need}.")
            for q in v.props:
                if q.key == "query" and q.value is not None and q.value.kind == "object":
                    self.query(q.value)
        elif name == "$vectorSearch" and v.kind == "object":
            self.objects.append((v, "stage"))
            have = {q.key for q in v.props}
            for need in ("index", "path", "limit"):
                if need not in have:
                    self.add(v.start, v.start + 1, ERROR, "missing-field", f"$vectorSearch requires {need}.")
            if "queryVector" not in have and "query" not in have:
                self.add(v.start, v.start + 1, ERROR, "missing-field", "$vectorSearch requires queryVector (or query for auto-embedding).")
            exact = next((q for q in v.props if q.key == "exact"), None)
            if "numCandidates" not in have and not (exact and exact.value is not None and exact.value.value is True):
                self.add(v.start, v.start + 1, WARNING, "missing-field",
                         "ANN $vectorSearch needs numCandidates (or set exact: true).")
        elif name == "$setWindowFields" and v.kind == "object":
            self.objects.append((v, "stage"))
            for q in v.props:
                if q.key == "output" and q.value is not None and q.value.kind == "object":
                    self.objects.append((q.value, "group"))
                    for o in q.value.props:
                        if o.value is not None:
                            self.accumulator(o)
        elif name in {"$bucket", "$bucketAuto"} and v.kind == "object":
            self.objects.append((v, "stage"))
            for q in v.props:
                if q.key == "groupBy" and q.value is not None:
                    self.expr(q.value)
                elif q.key == "output" and q.value is not None and q.value.kind == "object":
                    self.objects.append((q.value, "group"))
                    for o in q.value.props:
                        if o.value is not None:
                            self.accumulator(o)
        elif v.kind == "object" and name in {"$sample", "$merge", "$out", "$search", "$searchMeta", "$fill", "$densify"}:
            self.objects.append((v, "stage"))
            if name == "$sample" and not any(q.key == "size" for q in v.props):
                self.add(v.start, v.start + 1, ERROR, "missing-field", "$sample requires size.")

    def lookup(self, obj: Node) -> None:
        self.objects.append((obj, "lookup"))
        self.dups(obj)
        keys = {p.key: p for p in obj.props}
        for p in obj.props:
            if p.key not in {"from", "localField", "foreignField", "as", "let", "pipeline"}:
                self.on_prop(p, WARNING, "unknown-field", f"{p.key!r} is not a $lookup option.")
        if "as" not in keys:
            self.add(obj.start, obj.start + 1, ERROR, "missing-field", "$lookup requires as.")
        has_pipe = "pipeline" in keys
        if not has_pipe:
            for need in ("localField", "foreignField"):
                if need not in keys:
                    self.add(obj.start, obj.start + 1, ERROR, "missing-field",
                             f"$lookup without a pipeline requires {need}.")
        if "from" not in keys and not has_pipe:
            self.add(obj.start, obj.start + 1, ERROR, "missing-field", "$lookup requires from.")
        if has_pipe and keys["pipeline"].value is not None:
            self.pipeline(keys["pipeline"].value)
        if "let" in keys and keys["let"].value is not None and keys["let"].value.kind == "object":
            for q in keys["let"].value.props:
                if q.value is not None:
                    self.expr(q.value)

    # ---- symbols
    def symbols(self) -> list[Symbol]:
        out: list[Symbol] = []
        for st in self.statements:
            label = None
            kind = "variable" if st.decl else "method"
            if st.decl:
                label = st.decl
            else:
                label = self.chain_name(st.node)
            if label is None:
                continue
            kids: list[Symbol] = []
            for n in st.node.walk():
                if n.kind == "array" and id(n) in self.stage_syms and not any(
                    k.start <= n.start and n.end <= k.end for k in kids
                ):
                    kids.extend(self.stage_syms[id(n)])
            out.append(Symbol(label, kind, st.start, st.end, kids))
        return out

    @staticmethod
    def chain_name(node: Node) -> str | None:
        """Dotted name of the outermost ``db.coll.method(...)`` call in a chain."""
        n = node
        last_call = None
        while n is not None:
            if n.kind == "call":
                last_call = n
                n = n.target
            elif n.kind == "member":
                n = n.target
            else:
                break
        target = last_call.target if last_call else None
        # walk the first call from the root: db.orders.find(...)
        first = None
        n = node
        while n is not None:
            if n.kind == "call":
                if n.target is not None and n.target.kind == "member":
                    first = n
                n = n.target
            elif n.kind == "member":
                n = n.target
            else:
                break
        target = first.target if first else target
        if target is None:
            return None
        parts: list[str] = []
        while target is not None and target.kind == "member":
            parts.append(str(target.value))
            target = target.target
        if target is not None and target.kind == "ident":
            parts.append(str(target.value))
        return ".".join(reversed(parts)) or None


def analyze(text: str) -> Result:
    return Analyzer(text).run()
