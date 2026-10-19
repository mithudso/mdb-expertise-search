"""optimize — static MQL query optimizer (the offline subset of the deep MQL query optimizer audit).

``optimize(text)`` finds every ``db.<coll>.find/aggregate/count/update/delete/watch`` call (and
pipelines bound to ``const`` variables), runs the audit passes that need no cluster connection,
recommends ESR-ordered indexes, and applies the result-preserving rewrites in place. It loops
until no rewrite applies (cap 3), like the deep optimizer's convergence loop.

Pass names follow the deep-mongodb-mql-query-optimizer skill:
P2 index use & ESR, P3 selectivity & key order, P4 operator anti-patterns, P5 stage ordering,
P6 sort/limit/cursor economics, P7 projection, P8 pagination. Explain-based verification (P9) needs
a live cluster and is out of scope here; every impact claim is static and marked as such.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import Node, Prop, Statement, parse

BLOCKING, HIGH, MEDIUM, LOW = "blocking", "high", "medium", "low"
SEVERITY_ORDER = {BLOCKING: 0, HIGH: 1, MEDIUM: 2, LOW: 3}

_REF = "skills/mongodb-expert/references/"
REFS = {
    "shape": _REF + "mongodb-query-shape-optimization.md",
    "index": _REF + "mongodb-compound-index-design.md",
    "special": _REF + "mongodb-special-indexes-and-index-builds.md",
    "explain": _REF + "mongodb-explain-plans-and-query-planner.md",
    "planner": _REF + "mongodb-advanced-explain-and-planner-changes.md",
    "agg": _REF + "mongodb-aggregation-pipeline.md",
    "perf": _REF + "mongodb-query-performance.md",
    "optimizer": _REF + "deep-mongodb-mql-query-optimizer.md",
}

#: base methods we treat as a query target -> index of the filter argument (None = pipeline)
TARGET_METHODS: dict[str, int | None] = {
    "find": 0, "findOne": 0, "countDocuments": 0, "count": 0, "distinct": 1,
    "deleteOne": 0, "deleteMany": 0, "remove": 0, "findOneAndDelete": 0,
    "findOneAndUpdate": 0, "updateOne": 0, "updateMany": 0, "update": 0,
    "findOneAndReplace": 0, "replaceOne": 0,
    "aggregate": None, "watch": None,
}
_RANGE_OPS = {"$gt", "$gte", "$lt", "$lte"}
_NEG_OPS = {"$ne", "$nin", "$not"}
_EQ_KINDS = {"string", "number", "bool", "null", "call", "ident", "member", "array", "undefined"}
#: stages a later $match may be hoisted above when it does not read fields they produce
_TRANSPARENT = {"$sort", "$project", "$addFields", "$set", "$unset", "$lookup", "$unwind"}
#: key/value attribute-pattern sub-field pairs (dotted predicates may match across elements)
_KV_PAIRS = [{"k", "v"}, {"key", "value"}, {"name", "value"}, {"type", "value"}, {"n", "v"}]
_NUMERIC_STR = re.compile(r"[-+]?\d+(\.\d+)?")
IN_SORT_LIMIT = 201  # $in at/above this many values behaves like a range for index sort


@dataclass
class Finding:
    start: int
    end: int
    severity: str
    code: str
    pass_id: str
    message: str
    fix: str | None = None  # replacement text for [start, end) — only result-preserving rewrites
    ref: str | None = None  # corpus path with the background (mdbx show <ref>)


@dataclass
class IndexRec:
    collection: str
    keys: list[tuple[str, int]]
    rationale: str

    def shell(self) -> str:
        body = ", ".join(f"{_key(k)}: {d}" for k, d in self.keys)
        return f"db.{self.collection}.createIndex({{ {body} }})"


@dataclass
class Target:
    kind: str  # find | aggregate | write | count | distinct | watch
    collection: str
    method: str
    start: int
    end: int
    filter: Node | None = None
    projection: Node | None = None
    sort: Node | None = None
    pipeline: Node | None = None
    chain: dict[str, Node] = field(default_factory=dict)  # cursor method -> its call node


@dataclass
class Report:
    original: str
    text: str  # after applied rewrites
    targets: list[Target]
    findings: list[Finding]  # from the final iteration, plus the applied ones
    applied: list[Finding]
    indexes: list[IndexRec]
    iterations: int
    input_queries: int = 0  # queries found in the original text (a rewrite can retire one)

    @property
    def changed(self) -> bool:
        return self.text != self.original


def _key(k: str) -> str:
    return k if re.fullmatch(r"[A-Za-z_$][\w$]*", k) else repr(k).replace("'", '"')


@dataclass
class _Pred:
    field: str
    kind: str  # eq | in | range | regex | neg | exists | other
    n_in: int = 0


class _Audit:
    def __init__(self, text: str):
        self.text = text
        self.statements, _ = parse(text)
        self.vars: dict[str, Node] = {s.decl: s.node for s in self.statements if s.decl}
        self.findings: list[Finding] = []
        self.indexes: list[IndexRec] = []
        self.targets: list[Target] = []
        self.seen_pipelines: set[int] = set()

    def src(self, n: Node) -> str:
        return self.text[n.start : n.end]

    def add(self, node_or_span, sev: str, code: str, pid: str, msg: str, *, fix: str | None = None,
            ref: str = "shape") -> None:
        if isinstance(node_or_span, tuple):
            s, e = node_or_span
        elif isinstance(node_or_span, Prop):
            s, e = node_or_span.key_start, node_or_span.key_end
        else:
            s, e = node_or_span.start, node_or_span.end
        self.findings.append(Finding(s, max(e, s + 1), sev, code, pid, msg, fix, REFS.get(ref, ref)))

    def resolve(self, n: Node | None) -> Node | None:
        if n is not None and n.kind == "ident" and str(n.value) in self.vars:
            return self.vars[str(n.value)]
        return n

    # ---- target discovery
    def run(self) -> None:
        for st in self.statements:
            self.statement(st)

    def statement(self, st: Statement) -> None:
        tops = [c for c in st.node.walk() if c.kind == "call"]
        inner: set[int] = set()
        for c in tops:  # calls that are the callee of an outer chain call are not chain heads
            t = c.target
            while t is not None and t.kind in {"member", "call"}:
                if t.kind == "call":
                    inner.add(id(t))
                t = t.target
        for c in tops:
            if id(c) not in inner:
                self.chain(c)

    def chain(self, call: Node) -> None:
        calls: list[tuple[str, Node]] = []
        n: Node | None = call
        while n is not None and n.kind == "call" and n.target is not None and n.target.kind == "member":
            calls.append((str(n.target.value), n))
            n = n.target.target
        calls.reverse()
        coll = None
        if n is not None and n.kind == "member" and n.target is not None and n.target.kind == "ident" \
                and n.target.value == "db":
            coll = str(n.value)
        if calls and calls[0][0] == "getCollection" and n is not None and n.kind == "ident" and n.value == "db":
            args = calls[0][1].items
            coll = str(args[0].value) if args and args[0].kind == "string" else "collection"
            calls = calls[1:]
        if coll is None or not calls or calls[0][0] not in TARGET_METHODS:
            return
        method, base = calls[0]
        t = Target(self._kind(method), coll, method, call.start, call.end,
                   chain={name: c for name, c in calls[1:]})
        argi = TARGET_METHODS[method]
        if argi is None:
            t.pipeline = self.resolve(base.items[0]) if base.items else None
        else:
            if len(base.items) > argi:
                t.filter = self.resolve(base.items[argi])
            if method in {"find", "findOne"} and len(base.items) > 1:
                t.projection = self.resolve(base.items[1])
            if method == "findOneAndUpdate" and len(base.items) > 2:
                opts = base.items[2]
                for p in opts.props if opts.kind == "object" else []:
                    if p.key == "sort":
                        t.sort = p.value
                    if p.key == "projection":
                        t.projection = p.value
        if "sort" in t.chain and t.chain["sort"].items:
            t.sort = self.resolve(t.chain["sort"].items[0])
        if "projection" in t.chain and t.chain["projection"].items:
            t.projection = self.resolve(t.chain["projection"].items[0])
        self.targets.append(t)
        self.audit_target(t, base)

    @staticmethod
    def _kind(method: str) -> str:
        if method in {"find", "findOne"}:
            return "find"
        if method in {"count", "countDocuments"}:
            return "count"
        return {"aggregate": "aggregate", "watch": "watch", "distinct": "distinct"}.get(method, "write")

    # ---- per target
    def audit_target(self, t: Target, base: Node) -> None:
        preds: list[_Pred] = []
        has_sort = t.sort is not None and t.sort.kind == "object" and bool(t.sort.props)
        if t.filter is not None and t.filter.kind == "object":
            preds = self.filter(t.filter, has_sort=has_sort)
        if t.pipeline is not None and t.pipeline.kind == "array":
            if id(t.pipeline) in self.seen_pipelines:
                return
            self.seen_pipelines.add(id(t.pipeline))
            self.pipeline(t, t.pipeline)
            return
        self.cursor(t, base)
        if t.kind in {"find", "count", "distinct", "write"}:
            self.recommend(t, preds, t.sort, t.projection)

    def cursor(self, t: Target, base: Node) -> None:
        ch = t.chain
        skip = ch.get("skip")
        n = _num(skip.items[0]) if skip is not None and skip.items else None
        if n is not None and n >= 1000:
            self.add(skip, MEDIUM, "deep-skip", "P8",
                     f"skip({int(n)}) walks and discards {int(n)} index keys or documents on every page, and on "
                     "a sharded collection mongos asks each shard for limit+skip. Use keyset pagination: "
                     "sort on a unique key and filter { _id: { $gt: lastSeenId } } with limit().", ref="perf")
        if t.sort is not None and "limit" not in ch and t.kind == "find" and t.method == "find":
            self.add(ch.get("sort", base), LOW, "sort-no-limit", "P6",
                     "sort() without limit(): if no index supplies this order, the whole result is sorted in "
                     "memory (100 MB blocking-sort cap; spills or fails). Back the sort with an index or add a limit.",
                     ref="perf")
        if "hint" in ch:
            self.add(ch["hint"], LOW, "pinned-hint", "P2",
                     "hint() pins a plan in application code. Compare explain() with and without it; on 8.0+ "
                     "prefer setQuerySettings (persistent, per query shape) for an intentional pin.", ref="planner")
        bs = ch.get("batchSize")
        b = _num(bs.items[0]) if bs is not None and bs.items else None
        if b is not None and b < 20:
            self.add(bs, MEDIUM, "tiny-batch", "P6",
                     f"batchSize({int(b)}) multiplies getMore round-trips; on a change stream each getMore re-scans "
                     "the oplog window. Use the default (101 first batch, then up to 16 MiB) or a larger value.",
                     ref="perf")
        if t.method == "count":
            self.add(base.target, LOW, "legacy-count", "P6",
                     "count() is deprecated and can be inaccurate on sharded clusters: use countDocuments(filter), "
                     "or estimatedDocumentCount() for an unfiltered total (reads metadata only).", ref="perf")
        if t.method == "countDocuments" and (t.filter is None or (t.filter.kind == "object" and not t.filter.props)):
            self.add(base, MEDIUM, "count-all", "P6",
                     "countDocuments({}) scans the collection or the _id index. For a whole-collection total use "
                     "estimatedDocumentCount(), which reads collection metadata.",
                     fix=f"db.{t.collection}.estimatedDocumentCount()" if base.end == t.end else None, ref="perf")
        if t.method == "distinct":
            self.add(base.target, LOW, "distinct-16mb", "P6",
                     "distinct() returns one document capped at 16 MB and can use DISTINCT_SCAN only with an index "
                     "led by the field. For large or sharded results use $group.", ref="perf")

    # ---- filter (P3/P4)
    def filter(self, obj: Node, *, has_sort: bool, prefix: str = "", rooted: bool = True) -> list[_Pred]:
        preds: list[_Pred] = []
        dotted: dict[str, set[str]] = {}
        for p in obj.props:
            v = p.value
            if v is None:
                continue
            if p.key in {"$and"} and v.kind == "array":
                for it in v.items:
                    if it.kind == "object":
                        preds += self.filter(it, has_sort=has_sort, prefix=prefix, rooted=rooted)
            elif p.key in {"$or", "$nor"} and v.kind == "array":
                for it in v.items:
                    if it.kind == "object":
                        self.filter(it, has_sort=has_sort, prefix=prefix, rooted=False)
                if p.key == "$or":
                    self.or_rules(obj, p, has_sort=has_sort, rooted=rooted)
            elif p.key == "$where":
                self.add(p, HIGH, "where", "P4",
                         "$where runs JavaScript per document, cannot use an index, and is deprecated from 8.0. "
                         "Rewrite with native query operators or $expr.")
            elif p.key == "$expr":
                self.expr_rule(p)
            elif p.key == "$text" or p.key.startswith("$"):
                continue
            else:
                name = prefix + p.key
                if "." in p.key:
                    head, _, tail = p.key.rpartition(".")
                    dotted.setdefault(head, set()).add(tail)
                preds += self.field(p, name, has_sort=has_sort)
        for head, subs in dotted.items():
            pair = next((pr for pr in _KV_PAIRS if pr <= subs), None)
            if pair:
                k, v = sorted(pair, key=lambda x: x in {"v", "value"})  # key-ish name first
                span = next(p for p in obj.props if p.key.startswith(head + "."))
                self.add(span, BLOCKING, "kv-without-elemmatch", "P4",
                         f"Separate predicates on {head}.{k} and {head}.{v} can be satisfied by different elements of "
                         f"the {head} array, so an element {k}=a,{v}=1 next to {k}=b,{v}=2 matches {k}=a,{v}=2. Put "
                         f"both inside {{ {head}: {{ $elemMatch: {{ {k}: …, {v}: … }} }} }} and index "
                         f"{{ \"{head}.{k}\": 1, \"{head}.{v}\": 1 }}. Reported, not applied: it changes the result set.")
        return preds

    def field(self, p: Prop, name: str, *, has_sort: bool) -> list[_Pred]:
        v = p.value
        assert v is not None
        if v.kind == "regex":
            self.regex_rule(v, str(v.value).rsplit("/", 1)[0], str(v.value).rsplit("/", 1)[1])
            return [_Pred(name, "regex" if _anchored(str(v.value)) and "i" not in str(v.value).rsplit("/", 1)[1]
                          else "other")]
        if v.kind != "object" or not v.props or not all(q.key.startswith("$") for q in v.props):
            return [_Pred(name, "eq")]
        keys = {q.key: q for q in v.props}
        out: list[_Pred] = []
        # degenerate range: { $gte: X, $lte: X } is an equality
        lo, hi = keys.get("$gte"), keys.get("$lte")
        if lo and hi and lo.value is not None and hi.value is not None and \
                self.src(lo.value).strip() == self.src(hi.value).strip():
            only = len(v.props) == 2
            self.add(v, MEDIUM, "degenerate-range", "P4",
                     f"{name}: $gte and $lte carry the same value, which is an equality the planner treats as a "
                     "range (breaks ESR key order and invites near-tied plans). Rewrite to an equality.",
                     fix=self.src(lo.value) if only else None)
            return [_Pred(name, "eq")]
        for op, q in keys.items():
            qv = q.value
            if op in {"$eq"}:
                out.append(_Pred(name, "eq"))
            elif op == "$in" and qv is not None and qv.kind == "array":
                n = len(qv.items)
                out.append(_Pred(name, "in" if n < IN_SORT_LIMIT else "range", n))
                if n >= 10_000:
                    self.add(q, HIGH, "huge-in", "P4",
                             f"$in with {n} values: parse, plan and bounds cost grow with every value. Load the set "
                             "into a collection and $lookup, or batch the query.")
                elif n >= 1000:
                    self.add(q, MEDIUM, "large-in", "P4",
                             f"$in with {n} values: consider batching or a join collection.")
                elif n >= IN_SORT_LIMIT and has_sort:
                    self.add(q, MEDIUM, "in-blocks-sort", "P4",
                             f"$in with {n} values (>= {IN_SORT_LIMIT}) is planned like a range, so a following sort "
                             "cannot use SORT_MERGE over the index and becomes a blocking sort. Split the list or "
                             "keep it under 201 values.")
            elif op in _RANGE_OPS:
                if qv is not None and qv.kind == "string" and _NUMERIC_STR.fullmatch(str(qv.value)):
                    self.add(qv, BLOCKING, "string-numeric-compare", "P4",
                             f"{name} {op} \"{qv.value}\" compares strings lexicographically (\"10\" < \"2\"). If "
                             "the field holds numbers as strings, results are wrong; store numbers as numbers. "
                             "Reported, not applied.")
                out.append(_Pred(name, "range"))
            elif op in _NEG_OPS or (op == "$exists" and qv is not None and qv.kind == "bool" and not qv.value):
                self.add(q, MEDIUM, "negation", "P4",
                         f"{name}: {op}{'' if op != '$exists' else ': false'} cannot use selective index bounds and "
                         "also matches documents missing the field. Where the domain is known, match the wanted "
                         "values positively ($in / equality) — this changes results unless the field is always "
                         "present, so it is not auto-applied.")
                out.append(_Pred(name, "neg"))
            elif op == "$exists":
                out.append(_Pred(name, "exists"))
            elif op == "$regex":
                opts = keys.get("$options")
                flags = str(opts.value.value) if opts and opts.value is not None and opts.value.kind == "string" else ""
                pat = str(qv.value) if qv is not None and qv.kind in {"string", "regex"} else ""
                if qv is not None and qv.kind == "regex":
                    pat, _, f2 = pat.rpartition("/")
                    flags += f2
                if qv is not None:
                    self.regex_rule(qv, pat, flags)
                out.append(_Pred(name, "regex" if pat.startswith(("^", "\\A")) and "i" not in flags else "other"))
            elif op == "$elemMatch":
                out.append(_Pred(name, "other"))
        return out or [_Pred(name, "other")]

    def regex_rule(self, node: Node, pat: str, flags: str) -> None:
        if not pat.startswith(("^", "\\A")):
            self.add(node, MEDIUM, "unanchored-regex", "P4",
                     f"/{pat}/ is not anchored, so it scans every index key (or document). Anchor it with ^ if "
                     "the value is a prefix, or use Atlas Search for substring / full-text matching.")
        elif "i" in flags:
            self.add(node, MEDIUM, "case-insensitive-regex", "P4",
                     f"/{pat}/{flags}: a case-insensitive regex cannot use tight index bounds even when anchored. "
                     "Store a normalized lower-case copy, or query with a strength-2 collation that matches an "
                     "index built with the same collation.", ref="index")

    def or_rules(self, parent: Node, p: Prop, *, has_sort: bool, rooted: bool) -> None:
        v = p.value
        assert v is not None
        branches = [it for it in v.items if it.kind == "object"]
        fields = {b.props[0].key for b in branches if len(b.props) == 1}
        simple = all(len(b.props) == 1 and not b.props[0].key.startswith("$") and b.props[0].value is not None
                     and _is_eq_value(b.props[0].value) for b in branches)
        if len(branches) >= 2 and simple and len(fields) == 1:
            f = fields.pop()
            vals = ", ".join(self.src(b.props[0].value) for b in branches)  # type: ignore[arg-type]
            clash = any(q.key == f for q in parent.props)
            self.add((p.start, p.end), MEDIUM, "or-to-in", "P4",
                     f"$or of equalities on one field ({f}) is an $in: one index scan with point bounds instead "
                     "of a subplan per branch, and sort-compatible.",
                     fix=None if clash else f"{_key(f)}: {{ $in: [{vals}] }}")
            return
        if rooted and has_sort:
            self.add(p, MEDIUM, "rooted-or-sort", "P4",
                     "A top-level $or combined with a sort can pick a blocking SORT instead of merging sorted "
                     "branch scans (SERVER-19114). Prefer $in where the branches share a field, or give each "
                     "branch an index whose order matches the sort.")
        if len(branches) >= 2:
            self.add(p, LOW, "or-branch-indexes", "P2",
                     "The planner uses indexes for an $or only when EVERY branch has a usable index; one unindexed "
                     "branch turns the whole query into a collection scan. See the per-branch index "
                     "recommendations.", ref="index")

    def expr_rule(self, p: Prop) -> None:
        v = p.value
        if v is None or v.kind != "object" or len(v.props) != 1:
            return
        op = v.props[0].key
        args = v.props[0].value
        simple = op in {"$eq", "$lt", "$lte", "$gt", "$gte"} and args is not None and args.kind == "array" and \
            len(args.items) == 2 and sum(1 for a in args.items if a.kind == "string" and str(a.value).startswith("$")
                                         and not str(a.value).startswith("$$")) == 1
        if not simple:
            self.add(p, MEDIUM, "expr-unindexable", "P4",
                     f"$expr with {op} is evaluated per document and cannot use index bounds (only a plain "
                     "$eq/$lt/$lte/$gt/$gte of one field against a constant can). Rewrite with query operators "
                     "where equivalent, or precompute the value into a field at write time.")

    # ---- pipeline (P5)
    def pipeline(self, t: Target, arr: Node) -> None:
        stages = [(it.props[0].key, it.props[0].value, it) for it in arr.items
                  if it.kind == "object" and len(it.props) == 1]
        names = [s[0] for s in stages]
        if not stages:
            return
        # change streams: narrow first
        if t.kind == "watch" and names[0] != "$match":
            self.add(stages[0][2], MEDIUM, "changestream-match-first", "P5",
                     "Put the event-narrowing $match (operationType, ns, fields) first so it is pushed into the "
                     "oplog scan; otherwise every event flows through the later stages.", ref="agg")
        self.hoist_match(arr, stages)
        for i, (name, v, item) in enumerate(stages):
            if v is None:
                continue
            if name == "$match" and v.kind == "object":
                after_sort = i + 1 < len(stages) and stages[i + 1][0] == "$sort"
                self.filter(v, has_sort=after_sort)
            elif name == "$sample" and i > 0:
                self.add(item, MEDIUM, "sample-not-first", "P5",
                         "$sample uses a random cursor only as the first stage; later it reads and sorts the "
                         "whole input randomly.", ref="agg")
            elif name == "$skip":
                n = _num(v)
                if n is not None and n >= 1000:
                    self.add(item, MEDIUM, "deep-skip", "P8",
                             f"$skip {int(n)} still produces and discards {int(n)} documents per page; use keyset "
                             "pagination ($match on the last seen sort key).", ref="perf")
            elif name == "$sort":
                nxt = names[i + 1] if i + 1 < len(names) else None
                if i > 0 and names[i - 1] == "$search":
                    self.add(item, MEDIUM, "sort-after-search", "P5",
                             "$sort after $search materializes every search hit before sorting. Use the $search "
                             "`sort` option instead.", ref="agg")
                elif nxt not in {"$limit", "$group"} and "$limit" not in names[i + 1 : i + 3]:
                    self.add(item, LOW, "sort-no-limit", "P6",
                             "$sort is a blocking stage (100 MB per stage, then spills). Unless an index supplies "
                             "the order, follow it with $limit (top-k sort) or slim the stream first.", ref="agg")
            elif name == "$limit" and i > 0 and names[i - 1] == "$search":
                n = _num(v)
                if n is not None and n >= 1000:
                    self.add(item, MEDIUM, "search-overfetch", "P5",
                             f"$limit {int(n)} after $search over-fetches; size it to the page and use $searchMeta "
                             "for counts.", ref="agg")
            elif name == "$group" and v.kind == "object":
                self.group(stages, i, v)
            elif name == "$lookup" and v.kind == "object":
                self.lookup(t, v, item)
        self.recommend_pipeline(t, stages)

    def hoist_match(self, arr: Node, stages: list) -> None:
        for i, (name, v, item) in enumerate(stages):
            if name != "$match" or i == 0 or v is None or v.kind != "object":
                continue
            used = _match_fields(v)
            if used is None:
                continue
            j = i
            while j > 0 and stages[j - 1][0] in _TRANSPARENT and not (_produced(stages[j - 1]) & used):
                j -= 1
            if j == i:
                continue
            order = [s[2] for s in stages]
            order.insert(j, order.pop(i))
            fix = None
            if len(stages) == len(arr.items):
                fix = self._rebuild_array(arr, order)
            moved_over = ", ".join(s[0] for s in stages[j:i])
            self.add((item.start, item.end), MEDIUM, "match-not-early", "P5",
                     f"This $match reads none of the fields produced by {moved_over}, so it can run before them: "
                     "fewer documents flow through the pipeline and, at the front, it can use an index.",
                     fix=None, ref="agg")
            if fix is not None:  # whole-array rewrite, applied as a separate finding
                self.findings.append(Finding(arr.start, arr.end, MEDIUM, "match-not-early-rewrite", "P5",
                                             "Move $match ahead of " + moved_over + ".", fix, REFS["agg"]))
            return  # one hoist per iteration; the loop re-runs on the rewritten text

    def _rebuild_array(self, arr: Node, order: list[Node]) -> str:
        first, last = arr.items[0], arr.items[-1]
        inner = self.text[first.start : last.end]
        multiline = "\n" in inner
        if multiline:
            line_start = self.text.rfind("\n", 0, first.start) + 1
            indent = self.text[line_start : first.start]
            body = (",\n" + indent).join(self.src(n) for n in order)
        else:
            body = ", ".join(self.src(n) for n in order)
        return self.text[arr.start : first.start] + body + self.text[last.end : arr.end]

    def group(self, stages: list, i: int, v: Node) -> None:
        later = stages[i + 1 :]
        for p in v.props:
            if p.key == "_id" or p.value is None or p.value.kind != "object" or not p.value.props:
                continue
            acc = p.value.props[0]
            if acc.value is not None and acc.value.kind == "string" and acc.value.value == "$$ROOT":
                self.add(acc, HIGH if acc.key == "$push" else MEDIUM, "group-root", "P5",
                         f"{acc.key}: \"$$ROOT\" carries whole documents into $group memory (100 MB per stage). "
                         "$project only the fields you need first.", ref="agg")
            if acc.key == "$push" and any(_slices(s, p.key) for s in later):
                self.add(acc, HIGH, "push-then-slice", "P5",
                         f"{p.key} builds an unbounded array with $push and a later stage slices it. Use a bounded "
                         "accumulator ($firstN / $lastN / $topN / $bottomN, 5.2+) so the discarded elements are "
                         "never held in memory.", ref="agg")
        prev = stages[i - 1][0] if i > 0 else None
        accs = {p.value.props[0].key for p in v.props
                if p.key != "_id" and p.value is not None and p.value.kind == "object" and p.value.props}
        if prev == "$sort" and accs and accs <= {"$first", "$last"}:
            self.add(stages[i][2], LOW, "distinct-scan-eligible", "P5",
                     "$sort + $group with only $first/$last can run as a DISTINCT_SCAN (one index seek per group) "
                     "when an index matches the sort and group key — keep this shape and confirm with explain().",
                     ref="planner")
        elif i == 0:
            self.add(stages[i][2], LOW, "group-whole-collection", "P5",
                     "$group as the first stage reads the whole collection on every run. If this is a recurring "
                     "report, maintain a summary collection ($merge or on-write upsert).", ref="agg")

    def lookup(self, t: Target, v: Node, item: Node) -> None:
        opts = {p.key: p.value for p in v.props}
        frm, ff = opts.get("from"), opts.get("foreignField")
        if frm is not None and frm.kind == "string" and ff is not None and ff.kind == "string" \
                and ff.value != "_id":  # _id is always indexed
            self.indexes.append(IndexRec(str(frm.value), [(str(ff.value), 1)],
                                         f"$lookup from {t.collection} probes {frm.value}.{ff.value} once per "
                                         "input document; without this index each probe is a collection scan."))
        elif "pipeline" in opts and "localField" not in opts:
            self.add(item, LOW, "lookup-pipeline", "P5",
                     "Correlated $lookup pipeline: make sure its $match uses $expr $eq on an indexed field of the "
                     "foreign collection (or use localField/foreignField with pipeline, 5.0+).", ref="agg")

    # ---- index recommendation (P2/P3/P7)
    def recommend(self, t: Target, preds: list[_Pred], sort: Node | None, proj: Node | None,
                  why: str = "") -> None:
        if t.filter is not None and t.filter.kind == "object":
            ors = [p for p in t.filter.props if p.key == "$or" and p.value is not None and p.value.kind == "array"]
            if ors and not any(f.code == "or-to-in" for f in self.findings if f.start == ors[0].start):
                for b in ors[0].value.items:  # type: ignore[union-attr]
                    if b.kind == "object":
                        bp = preds + self.quiet_filter(b)
                        self._emit(t, bp, sort, proj, f"$or branch {self.src(b)[:60]}")
                if preds:
                    return
        self._emit(t, preds, sort, proj, why)

    def quiet_filter(self, obj: Node) -> list[_Pred]:
        saved = len(self.findings)
        out = self.filter(obj, has_sort=False, rooted=False)
        del self.findings[saved:]
        return out

    def _emit(self, t: Target, preds: list[_Pred], sort: Node | None, proj: Node | None, why: str) -> None:
        eq = _uniq(p.field for p in preds if p.kind in {"eq", "in"})
        rng = _uniq(p.field for p in preds if p.kind in {"range", "regex"} and p.field not in eq)
        srt: list[tuple[str, int]] = []
        if sort is not None and sort.kind == "object":
            for p in sort.props:
                d = _num(p.value)
                if d in {1, -1} and p.key not in eq:  # equality already fixes that key's order
                    srt.append((p.key, int(d)))
        keys = [(f, 1) for f in eq] + [(f, d) for f, d in srt if f not in eq]
        keys += [(f, 1) for f in rng if f not in {k for k, _ in keys}]
        if not keys:
            return
        parts = []
        if eq:
            parts.append("equality " + ", ".join(eq))
        if srt:
            parts.append("sort " + ", ".join(f for f, _ in srt))
        if rng:
            parts.append("range " + ", ".join(rng))
        rationale = "ESR order: " + " -> ".join(parts) + "."
        if srt and rng:
            rationale += (" If the range is far more selective than the sort saves, test the ERS order (range "
                          "before sort) with explain() at representative values.")
        if any(p.kind == "in" for p in preds) and srt:
            rationale += " $in under 201 values keeps the sort index-backed via SORT_MERGE."
        cover = _projection_fields(proj)
        if cover and set(cover) <= {k for k, _ in keys} and proj is not None:
            excl = any(p.key == "_id" and _num(p.value) == 0 for p in proj.props)
            rationale += " Covers the projection" + ("" if excl else " if you add _id: 0") + \
                " (PROJECTION_COVERED, 0 documents examined)."
        if why:
            rationale = f"[{why}] " + rationale
        rec = IndexRec(t.collection, keys, rationale)
        if [k for k, _ in keys] == ["_id"]:  # served by the built-in _id index
            return
        if all(r.shell() != rec.shell() for r in self.indexes):
            self.indexes.append(rec)

    def recommend_pipeline(self, t: Target, stages: list) -> None:
        if not stages or stages[0][0] not in {"$match", "$sort"}:
            return
        preds: list[_Pred] = []
        sort = None
        if stages[0][0] == "$match" and stages[0][1] is not None and stages[0][1].kind == "object":
            preds = self.quiet_filter(stages[0][1])
            if len(stages) > 1 and stages[1][0] == "$sort":
                sort = stages[1][1]
        else:
            sort = stages[0][1]
        fake = Target("find", t.collection, "aggregate", t.start, t.end)
        self._emit(fake, preds, sort, None, "leading $match/$sort")


def _num(n: Node | None) -> float | None:
    if n is None or n.kind != "number":
        return None
    try:
        return float(n.value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _anchored(regex_value: str) -> bool:
    return regex_value.startswith(("^", "\\A"))


def _is_eq_value(v: Node) -> bool:
    if v.kind in _EQ_KINDS:
        return True
    return v.kind == "object" and not any(p.key.startswith("$") for p in v.props)


def _uniq(items) -> list[str]:
    out: list[str] = []
    for i in items:
        if i not in out:
            out.append(i)
    return out


def _projection_fields(proj: Node | None) -> list[str]:
    if proj is None or proj.kind != "object":
        return []
    out = []
    for p in proj.props:
        if p.key == "_id":
            continue
        if _num(p.value) == 1 or (p.value is not None and p.value.kind == "bool" and p.value.value):
            out.append(p.key)
        else:
            return []  # exclusion or computed projection: not coverable
    return out


def _match_fields(v: Node) -> set[str] | None:
    """Top-level field roots a $match reads; None when it uses $expr/$where (reads arbitrary fields)."""
    out: set[str] = set()
    for p in v.props:
        if p.key in {"$expr", "$where", "$text", "$jsonSchema"}:
            return None
        if p.key in {"$and", "$or", "$nor"} and p.value is not None and p.value.kind == "array":
            for it in p.value.items:
                if it.kind != "object":
                    return None
                sub = _match_fields(it)
                if sub is None:
                    return None
                out |= sub
        elif not p.key.startswith("$"):
            out.add(p.key.split(".")[0])
    return out


def _produced(stage: tuple) -> set[str]:
    """Top-level field roots a stage creates or rewrites (so a later $match on them cannot move above it)."""
    name, v, _ = stage
    if v is None:
        return {"*"}
    if name in {"$addFields", "$set"} and v.kind == "object":
        return {p.key.split(".")[0] for p in v.props}
    if name == "$project" and v.kind == "object":
        out = set()
        for p in v.props:
            pv = p.value
            if pv is None or not (pv.kind in {"number", "bool"}):
                out.add(p.key.split(".")[0])  # computed / renamed field
        return out
    if name == "$lookup" and v.kind == "object":
        return {str(p.value.value).split(".")[0] for p in v.props
                if p.key == "as" and p.value is not None and p.value.kind == "string"} or {"*"}
    if name == "$unwind":
        path = v.value if v.kind == "string" else next(
            (p.value.value for p in v.props if p.key == "path" and p.value is not None), None)
        extra = {str(p.value.value) for p in (v.props if v.kind == "object" else [])
                 if p.key == "includeArrayIndex" and p.value is not None}
        return ({str(path).lstrip("$").split(".")[0]} if path else {"*"}) | extra
    if name == "$unset":
        names = [v] if v.kind == "string" else v.items if v.kind == "array" else []
        return {str(n.value).split(".")[0] for n in names if n.kind == "string"}
    return set()


def _slices(stage: tuple, fieldname: str) -> bool:
    _, v, _ = stage
    if v is None:
        return False
    for n in v.walk():
        if n.kind == "object":
            for p in n.props:
                if p.key == "$slice" and p.value is not None and p.value.kind == "array" and p.value.items:
                    a = p.value.items[0]
                    if a.kind == "string" and str(a.value) == "$" + fieldname:
                        return True
    return False


def _apply(text: str, findings: list[Finding]) -> tuple[str, list[Finding]]:
    fixes = sorted((f for f in findings if f.fix is not None), key=lambda f: (f.start, -(f.end - f.start)))
    chosen: list[Finding] = []
    last_end = -1
    for f in fixes:  # leftmost, then widest; skip overlaps (the loop picks them up next iteration)
        if f.start >= last_end:
            chosen.append(f)
            last_end = f.end
    for f in reversed(chosen):
        text = text[: f.start] + f.fix + text[f.end :]  # type: ignore[operator]
    return text, chosen


def optimize(text: str, *, apply: bool = True, max_iters: int = 3) -> Report:
    """Audit every query in ``text``; with ``apply`` rewrite in place until nothing changes (cap ``max_iters``)."""
    current = text
    applied: list[Finding] = []
    iters = 0
    while True:
        iters += 1
        audit = _Audit(current)
        audit.run()
        if iters == 1:
            n_input = len(audit.targets)
        if not apply or iters > max_iters:
            break
        new, chosen = _apply(current, audit.findings)
        if not chosen or new == current:
            break
        applied += chosen
        current = new
    audit.findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.start))
    return Report(text, current, audit.targets, audit.findings, applied, audit.indexes, iters, n_input)


def format_report(rep: Report, name: str = "<input>") -> str:
    """Human-readable report (used by `mdbx optimize`)."""
    out: list[str] = []
    t = rep.text
    counts = {s: sum(1 for f in rep.findings if f.severity == s) for s in SEVERITY_ORDER}
    out.append(f"MQL optimizer (static audit) — {name}: {rep.input_queries} quer{'y' if rep.input_queries == 1 else 'ies'}, "
               + (", ".join(f"{n} {s}" for s, n in counts.items() if n) or "no open findings")
               + (f"; {len(rep.applied)} rewrite(s) applied in {rep.iterations - 1} iteration(s)" if rep.applied else ""))
    if rep.applied:
        out.append("\nApplied rewrites (result-preserving):")
        for f in rep.applied:
            out.append(f"  ✓ [{f.pass_id} {f.code}] {f.message.split('. ')[0].rstrip('.')}.")
    if rep.findings:
        out.append("\nFindings:")
        for f in rep.findings:
            if f.fix is not None and f.code.endswith("-rewrite"):
                continue
            line = t.count("\n", 0, f.start) + 1
            col = f.start - (t.rfind("\n", 0, f.start) + 1) + 1
            out.append(f"  {name}:{line}:{col}: {f.severity.upper()} [{f.pass_id} {f.code}] {f.message}")
            if f.ref:
                out.append(f"      read more: mdbx show {f.ref}")
    if rep.indexes:
        out.append("\nRecommended indexes (recommend-only — build on non-prod first, check existing indexes):")
        for r in rep.indexes:
            out.append(f"  {r.shell()}\n      {r.rationale}")
    if rep.changed:
        out.append("\nRewritten query:\n" + rep.text.rstrip())
    out.append("\nStatic analysis only: confirm with explain('executionStats') — COLLSCAN -> IXSCAN, "
               "totalDocsExamined/nReturned near 1, nReturned unchanged.")
    return "\n".join(out)


def to_dict(rep: Report) -> dict:
    t = rep.text

    def pos(off: int) -> dict:
        return {"line": t.count("\n", 0, off) + 1, "column": off - (t.rfind("\n", 0, off) + 1) + 1}

    return {
        "queries": [{"kind": x.kind, "collection": x.collection, "method": x.method, **pos(x.start)}
                    for x in rep.targets],
        "findings": [{"severity": f.severity, "code": f.code, "pass": f.pass_id, "message": f.message,
                      "ref": f.ref, **pos(f.start)} for f in rep.findings if not f.code.endswith("-rewrite")],
        "applied": [{"code": f.code, "pass": f.pass_id, "message": f.message} for f in rep.applied],
        "indexes": [{"collection": r.collection, "keys": dict(r.keys), "shell": r.shell(),
                     "rationale": r.rationale} for r in rep.indexes],
        "rewritten": rep.text if rep.changed else None,
        "iterations": rep.iterations,
    }
