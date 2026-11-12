from pathlib import Path

from mdbx.cli import main
from mdbx.mql.optimize import format_report, optimize, to_dict
from mdbx.mql.server import optimizer_diagnostics

ROOT = Path(__file__).resolve().parents[1]


def codes(src: str) -> set[str]:
    return {f.code for f in optimize(src, apply=False).findings}


def test_where_and_string_numeric():
    c = codes('db.c.find({ $where: "this.a > 1", qty: { $gte: "10" } })')
    assert {"where", "string-numeric-compare"} <= c


def test_regex_rules():
    assert "unanchored-regex" in codes("db.c.find({ name: /smith/ })")
    assert "case-insensitive-regex" in codes("db.c.find({ name: /^smith/i })")
    assert "unanchored-regex" in codes('db.c.find({ name: { $regex: "smith" } })')
    assert not codes("db.c.find({ name: /^smith/ })") & {"unanchored-regex", "case-insensitive-regex"}


def test_negation_and_kv():
    assert "negation" in codes('db.c.find({ s: { $ne: "x" } })')
    assert "negation" in codes("db.c.find({ s: { $exists: false } })")
    assert "kv-without-elemmatch" in codes('db.c.find({ "a.k": "c", "a.v": 1 })')
    assert "kv-without-elemmatch" not in codes('db.c.find({ "addr.city": "x", "addr.zip": 1 })')


def test_in_thresholds():
    vals = ", ".join(str(i) for i in range(250))
    assert "in-blocks-sort" in codes(f"db.c.find({{ a: {{ $in: [{vals}] }} }}).sort({{ b: 1 }})")
    assert "in-blocks-sort" not in codes(f"db.c.find({{ a: {{ $in: [{vals}] }} }})")
    big = ", ".join(str(i) for i in range(1000))
    assert "large-in" in codes(f"db.c.find({{ a: {{ $in: [{big}] }} }})")


def test_or_to_in_rewrite_and_clash():
    rep = optimize("db.c.find({ $or: [{ a: 1 }, { a: 2 }] })")
    assert rep.text == "db.c.find({ a: { $in: [1, 2] } })"
    assert [f.code for f in rep.applied] == ["or-to-in"]
    clash = optimize("db.c.find({ a: { $gt: 0 }, $or: [{ a: 1 }, { a: 2 }] })")
    assert not clash.changed  # rewriting would create a duplicate key


def test_rooted_or_sort():
    assert "rooted-or-sort" in codes("db.c.find({ $or: [{ a: 1 }, { b: 2 }] }).sort({ c: 1 })")


def test_degenerate_range():
    source = "db.c.find({ t: { $gte: 5, $lte: 5 } })"
    rep = optimize(source)
    assert rep.text == source and not rep.applied
    assert "degenerate-range" in {f.code for f in rep.findings}


def test_expr_rule():
    assert "expr-unindexable" in codes('db.c.find({ $expr: { $gt: ["$a", "$b"] } })')
    assert "expr-unindexable" not in codes('db.c.find({ $expr: { $gt: ["$a", 5] } })')


def test_cursor_rules():
    c = codes("db.c.find({ a: 1 }).sort({ b: 1 }).skip(5000).batchSize(2).hint({ a: 1 })")
    assert {"deep-skip", "tiny-batch", "pinned-hint", "sort-no-limit"} <= c
    assert "legacy-count" in codes("db.c.count({ a: 1 })")
    rep = optimize("db.c.countDocuments({})")
    assert rep.text == "db.c.countDocuments({})" and not rep.applied
    assert "count-all" in {f.code for f in rep.findings}


def test_match_hoist_respects_produced_fields():
    src = "db.c.aggregate([{ $addFields: { d: 1 } }, { $sort: { t: 1 } }, { $match: { x: 1 } }])"
    rep = optimize(src)
    assert rep.text == "db.c.aggregate([{ $match: { x: 1 } }, { $addFields: { d: 1 } }, { $sort: { t: 1 } }])"
    blocked = "db.c.aggregate([{ $addFields: { d: 1 } }, { $match: { d: 1 } }])"
    assert not optimize(blocked).changed
    lookup = ('db.c.aggregate([{ $lookup: { from: "u", localField: "a", foreignField: "b", as: "u" } }, '
              '{ $match: { "u.x": 1 } }])')
    assert not optimize(lookup).changed


def test_match_hoist_multiline_keeps_layout():
    src = "db.c.aggregate([\n  { $sort: { t: 1 } },\n  { $match: { x: 1 } }\n])"
    assert optimize(src).text == "db.c.aggregate([\n  { $match: { x: 1 } },\n  { $sort: { t: 1 } }\n])"


def test_group_rules():
    src = ('db.c.aggregate([{ $group: { _id: "$k", docs: { $push: "$$ROOT" } } }, '
           '{ $project: { top: { $slice: ["$docs", 3] } } }])')
    assert {"group-root", "push-then-slice", "group-whole-collection"} <= codes(src)
    ds = 'db.c.aggregate([{ $sort: { k: 1, t: -1 } }, { $group: { _id: "$k", last: { $first: "$v" } } }])'
    assert "distinct-scan-eligible" in codes(ds)


def test_pipeline_stage_rules():
    assert "sample-not-first" in codes("db.c.aggregate([{ $match: { a: 1 } }, { $sample: { size: 5 } }])")
    assert "sort-after-search" in codes("db.c.aggregate([{ $search: { text: {} } }, { $sort: { a: 1 } }])")
    assert "changestream-match-first" in codes("db.c.watch([{ $project: { a: 1 } }])")


def test_variable_pipeline_and_get_collection():
    src = 'const p = [{ $match: { a: /x/ } }]\ndb.getCollection("orders").aggregate(p)'
    rep = optimize(src, apply=False)
    assert rep.targets[0].collection == "orders"
    assert "unanchored-regex" in {f.code for f in rep.findings}


def test_esr_index_and_covered():
    rep = optimize("db.o.find({ c: 1, t: { $gt: 5 } }, { c: 1, s: 1, t: 1, _id: 0 }).sort({ s: -1 }).limit(5)")
    rec = rep.indexes[0]
    assert rec.shell() == 'db.getCollection("o").createIndex({ c: 1, s: -1, t: 1 })'
    assert "ERS" in rec.rationale and "May cover the projection" in rec.rationale and "Confirm coverage with explain()" in rec.rationale
    assert "add _id: 0" not in rec.rationale


def test_or_branch_indexes():
    rep = optimize("db.o.find({ $or: [{ a: 1 }, { b: 2 }] })")
    shells = {r.shell() for r in rep.indexes}
    assert {'db.getCollection("o").createIndex({ a: 1 })', 'db.getCollection("o").createIndex({ b: 1 })'} <= shells


def test_lookup_index():
    rep = optimize('db.o.aggregate([{ $lookup: { from: "u", localField: "a", foreignField: "uid", as: "x" } }])')
    assert any(r.shell() == 'db.getCollection("u").createIndex({ uid: 1 })' for r in rep.indexes)


def test_lsp_diagnostics_and_toggle(monkeypatch):
    monkeypatch.setenv("MDBX_LSP_OPTIMIZE", "1")
    diags = optimizer_diagnostics("db.c.find({ name: /x/ })")
    assert any(d.code == "opt/unanchored-regex" and d.severity == "info" for d in diags)
    monkeypatch.setenv("MDBX_LSP_OPTIMIZE", "0")
    assert optimizer_diagnostics("db.c.find({ name: /x/ })") == []


def test_report_and_dict():
    rep = optimize((ROOT / "examples/slow-queries.mql").read_text())
    text = format_report(rep, "slow-queries.mql")
    assert "BLOCKING" in text and "Rewritten query" in text and "createIndex" in text
    d = to_dict(rep)
    assert d["rewritten"] and d["iterations"] >= 2 and len(d["queries"]) == 5
    assert len(optimize(rep.original, apply=False).targets) == 5


def test_cli(tmp_path, capsys):
    f = tmp_path / "q.mql"
    source = "db.c.find({ $or: [{ t: 1 }, { t: 2 }] })"
    f.write_text(source)
    assert main(["optimize", str(f)]) == 0
    assert "Rewritten query" in capsys.readouterr().out
    assert f.read_text() == source
    assert main(["optimize", "--write", str(f)]) == 0
    assert f.read_text() == "db.c.find({ t: { $in: [1, 2] } })"
    read_only_source = 'db.c.find({ $where: "1" })'
    f.write_text(read_only_source)
    assert main(["opt", "--read-only", str(f)]) == 1
    assert f.read_text() == read_only_source


def test_never_raises_on_garbage():
    for src in ["", "db.", "db.c.find(", "db.c.aggregate([{", "db.c.find({ $or: 3 })", "{{{",
                "db.c.find({a:{$in:4}})", "db.c.aggregate([{ $unwind: {} }, { $match: { a: 1 } }])"]:
        optimize(src)


def test_refs_exist_in_corpus():
    from mdbx.mql.optimize import REFS

    for ref in REFS.values():
        assert (ROOT / "corpus" / ref).is_file(), ref


def test_no_id_index_and_kv_names():
    rep = optimize('db.o.aggregate([{ $lookup: { from: "s", localField: "a", foreignField: "_id", as: "x" } }])')
    assert not rep.indexes
    assert not optimize("db.o.find({ _id: 5 })").indexes
    msg = next(f.message for f in optimize('db.p.find({ "attrs.name": "c", "attrs.value": 1 })').findings
               if f.code == "kv-without-elemmatch")
    assert '"attrs.name": 1, "attrs.value": 1' in msg


# Synthetic regressions for rewrite safety and recommendation identity.
def test_adversarial_rewrites_preserve_source():
    from mdbx.mql.parser import parse
    sources = [
        'db.c.countDocuments({}, {limit:1})',
        'db.c.find({a:{$gte:5,$lte:5}})',
        'const branch={b:1}; db.c.find({$or:[{a:1},{a:2},branch]})',
        'db.c.deleteMany({$or:[{a:1},false,{a:2}]})',
        'db.c.aggregate([{$project:{a:0}},{$match:{a:1}}])',
        'db.c.aggregate([{$project:{keep:1}},{$match:{a:1}}])',
        'const fields={a:0}; db.c.aggregate([{$set:fields},{$match:{a:1}}])',
        'db.c.aggregate([{$unset:fields},{$match:{a:1}}])',
    ]
    for source in sources:
        assert optimize(source).text == source
    source = 'db.c.aggregate([{$sort:{a:1}},// keep comment\n  {$match:{b:1}}])'
    report = optimize(source)
    assert report.text.count('db.c.aggregate(') == 1
    assert '// keep comment\n' in report.text
    assert not parse(report.text)[1]
    assert len(report.targets) == report.input_queries == 1


def test_generated_identifiers_are_data():
    import json

    from mdbx.mql.optimize import IndexRec, _key
    for key in ["a'b", 'a"b', 'x":1});__audit_marker=1;//', 'a\nb']:
        assert json.loads(_key(key)) == key
    for collection in ('orders-2026', 'getCollection', 'c;__audit_marker=1;//'):
        assert IndexRec(collection, [('a', 1)], '').shell() == \
            'db.getCollection(' + json.dumps(collection) + ').createIndex({ a: 1 })'
    source = 'db.getCollection(name).find({a:1})'
    report = optimize(source)
    assert report.text == source and report.targets[0].collection is None
    assert not report.indexes


def test_recommendations_follow_bindings_and_each_target():
    report = optimize('var f={a:1}; db.c.find(f); var f={b:1}; db.c.find(f);', apply=False)
    assert [r.keys for r in report.indexes] == [[('a', 1)], [('b', 1)]]
    report = optimize('const p=[{$match:{x:1}}]; db.a.aggregate(p); db.b.aggregate(p)', apply=False)
    assert {r.collection for r in report.indexes} == {'a', 'b'}
    assert optimize('db.c.find({$or:[{a:1},{a:2}]})', apply=False).indexes[0].keys == [('a', 1)]
    for method, args in [('findOneAndDelete', '{tenant:1},{sort:{score:-1}}'),
                         ('findOneAndReplace', '{tenant:1},{x:2},{sort:{score:-1}}')]:
        assert optimize(f'db.c.{method}({args})', apply=False).indexes[0].keys == [('tenant', 1), ('score', -1)]


def test_numeric_bounds_and_advice():
    from types import SimpleNamespace

    from mdbx.mql.optimize import _evidence_findings, _num
    for value in ('1e309', 10**400):
        assert _num(SimpleNamespace(kind='number', value=value)) is None
    for value in (float('inf'), 10**400):
        assert not any(f.code == 'log-scan-ratio' for f in _evidence_findings({'docsExamined':value, 'nreturned':1}, 0, 1))
    source = 'db.c.find({' + ','.join(f'k{i}:{i}' for i in range(33)) + '})'
    report = optimize(source, apply=False)
    assert not report.indexes and any(f.code == 'index-too-wide' for f in report.findings)
    assert 'expr-unindexable' in codes('db.c.find({$expr:{$eq:["$a",{$add:["$b",1]}]}})')
    assert 'unanchored-regex' in codes('db.c.find({x:/^a|b/})')
    assert 'unanchored-regex' in codes('db.c.find({x:/^a/m})')
    finding = next(f for f in optimize('db.c.find({a:{$ne:null}})').findings if f.code == 'negation')
    assert 'matches documents missing the field' not in finding.message
    finding = next(f for f in optimize('db.c.find({a:/^abc/i})').findings if f.code == 'case-insensitive-regex')
    assert 'not collation-aware' in finding.message


def test_evidence_stays_with_original_query():
    source = '{attr:{command:{count:"a",query:{}},planSummary:"COLLSCAN"}}\n{attr:{command:{find:"b",filter:{b:1}},planSummary:"IXSCAN"}}'
    result = to_dict(optimize(source))
    assert [q['evidence']['planSummary'] for q in result['queries']] == ['COLLSCAN', 'IXSCAN']


def test_evidence_identity_survives_edits_and_retired_targets(monkeypatch):
    import importlib
    module = importlib.import_module('mdbx.mql.optimize')
    source = '{attr:{command:{find:"a",filter:{$or:[{a:1},{a:2}]}},planSummary:"COLLSCAN"}}\n{attr:{command:{find:"b",filter:{b:1}},planSummary:"IXSCAN"}}'
    report = optimize(source)
    assert report.applied
    assert [q['evidence']['planSummary'] for q in to_dict(report)['queries']] == ['COLLSCAN', 'IXSCAN']
    original_cursor = module._Audit.cursor
    def retire(self, target, base):
        original_cursor(self, target, base)
        if target.collection == 'a':
            self.add((target.start,target.end), module.MEDIUM, 'synthetic-retire', 'P6', 'Retire synthetic target.',
                     fix='db.a.estimatedDocumentCount()')
    monkeypatch.setattr(module._Audit, 'cursor', retire)
    result = to_dict(optimize(source))
    assert [(q['collection'], q['evidence']['planSummary']) for q in result['queries']] == [('b','IXSCAN')]


def test_example_join_and_coverage_contracts():
    report = optimize((ROOT / 'examples/slow-queries.mql').read_text(), apply=False)
    aggregate = next(t for t in report.targets if t.method == 'aggregate')
    stages = {stage.props[0].key:stage.props[0].value for stage in aggregate.pipeline.items}
    lookup = {p.key:p.value for p in stages['$lookup'].props}
    assert lookup['localField'].value == 'top.uid'
    assert lookup['localField'].value.split('.')[0] in {p.key for p in stages['$project'].props}
    target = next(t for t in report.targets if t.collection == 'orders' and t.projection is not None)
    projection = {p.key:p.value.value for p in target.projection.props}
    assert projection['_id'] == 0
    index = next(r for r in report.indexes if r.collection == 'orders' and ('customerId',1) in r.keys)
    assert {k for k,v in projection.items() if v == 1} <= {k for k,_ in index.keys}


def test_recommendation_deduplication_is_linear(monkeypatch):
    import importlib
    module = importlib.import_module('mdbx.mql.optimize')
    comparisons = []
    class Name(str):
        def __eq__(self, other):
            comparisons.append(1)
            return super().__eq__(other)
        __hash__ = str.__hash__
    n = 200
    audit = module._Audit('')
    for repeat in range(2):
        for i in range(n):
            target = module.Target('find', Name(f'c{i}'), 'find', 0, 0)
            audit._emit(target, [module._Pred('a', 'eq')], None, None, '')
    assert len(audit.indexes) == n
    assert len(comparisons) <= 4 * n
