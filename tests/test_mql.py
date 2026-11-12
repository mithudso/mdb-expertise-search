import pytest

from mdbx.mql import features, operators
from mdbx.mql.analyze import analyze
from mdbx.mql.parser import parse


def codes(src: str) -> list[str]:
    return [d.code for d in analyze(src).diagnostics]


def msgs(src: str) -> list[str]:
    return [d.message for d in analyze(src).diagnostics]


def test_operator_table_loads():
    assert len(operators.OPERATORS) > 250
    assert operators.get("$merge").arg == "string|object"
    assert "$match" in operators.STAGES and "$set" in operators.UPDATE_OPS
    assert operators.suggest("$grup") == ["$group"]


def test_parser_relaxed_syntax():
    src = "db.c.find({ a: /x+/i, 'b': ISODate(\"2020-01-01\"), c: [1, -2.5, 0x10] }).limit(3) // tail"
    stmts, errs = parse(src)
    assert not errs and len(stmts) == 1 and stmts[0].node.kind == "call"


def test_parser_recovers_from_unclosed_brace():
    stmts, errs = parse("db.c.find({ a: 1, ")
    assert errs and stmts  # tree still produced for editor features


@pytest.mark.parametrize(
    "src",
    [
        'db.c.find({ a: { $gt: 1, $lt: 5 }, $or: [{ b: 1 }, { c: 2 }] })',
        'db.c.aggregate([{ $match: { s: "A" } }, { $group: { _id: "$k", n: { $sum: 1 } } }, { $sort: { n: -1 } }, { $limit: 5 }])',
        'db.c.updateOne({ _id: 1 }, { $set: { a: 1 }, $inc: { n: 1 }, $push: { xs: { $each: [1, 2], $slice: -5 } } })',
        'db.c.aggregate([{ $lookup: { from: "o", localField: "a", foreignField: "b", as: "x" } }, { $unwind: "$x" }, { $out: "z" }])',
        'db.c.find({ _id: { $oid: "507f1f77bcf86cd799439011" } })',
        'db.c.find({ t: { $regex: "^a", $options: "i" } }, { a: 1, b: 1 })',
    ],
)
def test_valid_mql_has_no_diagnostics(src):
    assert codes(src) == []


def test_unknown_operator_suggests_fix():
    d = analyze("db.c.find({ a: { $gtt: 1 } })").diagnostics
    assert d[0].code == "unknown-operator" and d[0].fix == "$gt" and d[0].severity == "error"


@pytest.mark.parametrize(
    "src,code",
    [
        ("db.c.aggregate([{ $group: { n: { $sum: 1 } } }])", "missing-field"),
        ("db.c.aggregate([{ $sort: { a: 2 } }])", "bad-argument"),
        ('db.c.aggregate([{ $unwind: "items" }])', "bad-argument"),
        ('db.c.aggregate([{ $out: "x" }, { $limit: 1 }])', "stage-position"),
        ("db.c.aggregate([{ $limit: 1 }, { $geoNear: { near: [0,0], distanceField: 'd' } }])", "stage-position"),
        ("db.c.aggregate([{ $match: { a: 1 }, $limit: 1 }])", "stage-shape"),
        ("db.c.aggregate([{ $project: { a: 1, b: 0 } }])", "projection-mix"),
        ("db.c.aggregate({ $match: {} })", "bad-argument"),
        ("db.c.aggregate([{ $gt: 1 }])", "misplaced-operator"),
        ("db.c.updateOne({}, { $set: { a: 1 }, b: 2 })", "update-shape"),
        ("db.c.updateOne({}, { a: 1 })", "update-shape"),
        ("db.c.updateOne({}, { $pushAll: { a: [1] } })", "removed-operator"),
        ("db.c.find({ a: { $in: 5 } })", "bad-argument"),
        ("db.c.find({ $or: [] })", "bad-argument"),
        ("db.c.find({ $gt: 5 })", "misplaced-operator"),
        ("db.c.find({ a: 1, a: 2 })", "duplicate-key"),
        ('db.c.aggregate([{ $match: { $where: "1" } }])', "misplaced-operator"),
        ('db.c.aggregate([{ $match: { a: 1 } }, { $match: { $text: { $search: "x" } } }])', "stage-position"),
        ("db.c.aggregate([{ $lookup: { from: 'o', as: 'x' } }])", "missing-field"),
        ("db.c.aggregate([{ $facet: { a: [{ $out: 'z' }] } }])", "stage-position"),
        ("db.c.updateOne({}, [{ $match: { a: 1 } }])", "stage-position"),
        ("db.c.find({ a: { $exists: 'yes' } })", "bad-argument"),
        ("db.c.find({ a: 1", "syntax"),
    ],
)
def test_diagnostics(src, code):
    assert code in codes(src), analyze(src).diagnostics


def test_variable_pipeline_is_analyzed_with_call_context():
    src = "const p = [{ $group: { n: { $sum: 1 } } }]\ndb.c.aggregate(p)"
    assert "missing-field" in codes(src)
    # analysed once, not twice
    assert codes(src).count("missing-field") == 1


def test_bare_pipeline_array_detected():
    assert "stage-position" in codes('[{ $out: "x" }, { $limit: 1 }]')


def test_symbols_outline_pipeline_stages():
    r = analyze("db.orders.aggregate([{ $match: {a:1} }, { $limit: 2 }])")
    assert r.symbols[0].name == "db.orders.aggregate"
    assert [c.name for c in r.symbols[0].children] == ["$match", "$limit"]


def complete(marked: str) -> list[str]:
    off = marked.index("|")
    r = analyze(marked.replace("|", ""))
    return [c.label for c in features.completions(r, off)]


def test_completion_by_context():
    assert "$match" in complete("db.c.aggregate([ { $ma| } ])")
    assert "$gt" in complete("db.c.find({ a: { $| } })")
    assert "$set" in complete("db.c.updateOne({}, { $| })")
    assert "$each" in complete("db.c.updateOne({}, { $push: { a: { $| } } })")
    assert "$sum" in complete('db.c.aggregate([{ $group: { _id: 1, n: { $| } } }])')
    assert "$$NOW" in complete('db.c.aggregate([{ $set: { a: "$$|" } }])')
    assert "aggregate" in complete("db.c.agg|")
    assert complete('db.c.find({ a: "x|" })') == []  # inside a value


def test_hover_documents_operators_and_variables():
    assert "Left outer join" in features.hover_markdown("$lookup")
    assert "system variable" in features.hover_markdown("$$ROOT")
    assert features.hover_markdown("notanop") is None
    md = features.hover_markdown("$match", lambda t: ["`a.md:1` — x"])
    assert "Related expertise" in md


def test_word_at():
    assert features.word_at("{ $match: 1 }", 4)[0] == "$match"


@pytest.mark.parametrize("source", ["[1 2]", "{a:1 b:2}", "f(1 2)", "{,a:1}", "f(,1)", "@\n{x:1}"])
def test_parser_reports_malformed_transitions(source):
    statements, errors = parse(source)
    assert statements and errors


def test_parser_values_spans_and_escapes():
    src = 'new Date(0)'
    statements, errors = parse(src)
    assert not errors
    assert src[statements[0].node.start:statements[0].node.end] == src
    statements, errors = parse(r'{"\u0024match":{"tag":"\x61\b\f\v\0","face":"\uD83D\uDE00"}}')
    assert not errors
    prop = statements[0].node.props[0]
    assert prop.key == '$match'
    assert [p.value.value for p in prop.value.props] == ['a\b\f\v\0', '\U0001f600']
    for source in (r'"\uZZZZ"', r'"\xGG"', r'"\u{110000}"'):
        assert parse(source)[1]
    statements, errors = parse('db.c.find({ c: [1, -2.5, 0x10] })')
    assert not errors
    values = statements[0].node.items[0].props[0].value.items
    assert [(n.kind, n.value) for n in values] == [('number', 1), ('number', -2.5), ('number', 16)]


def test_parser_identifier_boundaries_and_line_comments():
    for name in ('NaNFilter', 'InfinityLimit'):
        statements, errors = parse(name)
        assert not errors and len(statements) == 1
        assert (statements[0].node.kind, statements[0].node.value) == ('ident', name)
    for terminator in ('\r', '\u2028', '\u2029'):
        statements, errors = parse('// note' + terminator + '{x:1}')
        assert not errors and len(statements) == 1
        assert statements[0].node.props[0].key == 'x'


def test_parser_bounded_nesting_and_iterative_walk():
    statements, errors = parse('[' * 2000 + '0' + ']' * 2000)
    assert errors
    statements, errors = parse('root' + '.x' * 2000)
    assert not errors
    nodes = list(statements[0].node.walk())
    assert len(nodes) == 2001 and nodes[-1].value == 'root'
    statements, errors = parse('9' * 5000)
    assert errors or isinstance(statements[0].node.value, (int, float))


@pytest.mark.parametrize('source', ['{a: @"}", b:1}', '{a:[f(1], b:2}', '{a: @/* } */ 0, b:1}'])
def test_parser_recovery_preserves_siblings(source):
    statements, errors = parse(source)
    assert errors
    assert [p.key for p in statements[0].node.props] == ['a', 'b']


@pytest.mark.parametrize('source', [
    'db.c.aggregate(42)', 'db.c.aggregate(true)', 'db.c.aggregate(null)', 'db.c.aggregate("bad")',
    'db.c.find({},[])', 'db.c.find({}).sort(false)',
    'db.c.aggregate([{$out:7}])', 'db.c.aggregate([{$merge:7}])', 'db.c.aggregate([{$unionWith:7}])',
    'db.c.find({$jsonSchema:7})', 'db.c.find({$sampleRate:"bad"})',
    'db.c.aggregate([{$project:{x:{$subtract:1}}}])', 'db.c.aggregate([{$project:{x:{$divide:1}}}])',
    'db.c.updateOne({},{$inc:{n:{value:1}}})', 'db.c.updateOne({},{$mul:{n:{value:1}}})',
    'db.c.find({a:{$size:-1}})',
])
def test_argument_boundaries(source):
    assert 'bad-argument' in codes(source)


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '1e309', '9' * 400])
def test_invalid_numeric_bounds_are_diagnostics(value):
    assert 'bad-argument' in codes('db.c.aggregate([{$limit:' + value + '}])')
    assert 'bad-argument' in codes('db.c.find({$sampleRate:' + value + '})')


def test_each_variable_use_context_is_validated():
    calls = ['db.c.aggregate(p);', 'db.c.updateOne({},p);']
    for order in (calls, calls[::-1]):
        assert codes('const p=[{$match:{}}];' + ''.join(order)).count('stage-position') == 1
    calls = ['db.c.find(d);', 'db.c.updateOne({},d);']
    for order in (calls, calls[::-1]):
        assert codes('const d={x:1};' + ''.join(order)).count('update-shape') == 1


def test_context_specific_operators_and_root_id():
    for src in ('db.c.aggregate([{$group:{_id:null,n:{$abs:"$n"}}}])',
                'db.c.aggregate([{$project:{n:{$push:"$n"}}}])',
                'db.c.aggregate([{$project:{n:{$sampleRate:0.5}}}])'):
        assert 'misplaced-operator' in codes(src)
    assert 'projection-mix' in codes('db.c.find({},{keep:1,nested:{_id:0}})')
    assert codes('db.c.find({},{keep:1,_id:0})') == []
    for op in ('$near', '$nearSphere'):
        src = 'db.c.aggregate([{$match:{$or:[{loc:{' + op + ':{$geometry:{type:"Point",coordinates:[0,0]}}}}]}}])'
        assert any(d.code == 'misplaced-operator' and '$match' in d.message for d in analyze(src).diagnostics)
    assert codes('db.c.find({$sampleRate:0.5})') == []
    assert codes('db.c.find({a:{$size:0}})') == []
    assert codes('db.c.updateOne({},{$inc:{n:{$numberInt:"1"}}})') == []


def test_window_output_has_separate_shape():
    assert codes('db.c.aggregate([{$setWindowFields:{sortBy:{t:1},output:{total:{$sum:"$n",window:{documents:["unbounded","current"]}}}}}])') == []
    assert 'bad-argument' in codes('db.c.aggregate([{$setWindowFields:{output:{total:{$sum:1,window:7}}}}])')


def test_pipeline_registration_uses_constant_time_membership():
    from mdbx.mql.analyze import Analyzer
    class CountedArrays(list):
        visits = 0
        def __contains__(self, target):
            for item in list.__iter__(self):
                self.visits += 1
                if item == target:
                    return True
            return False
        def __iter__(self):
            for item in super().__iter__():
                self.visits += 1
                yield item
    analyzer = Analyzer('db.c.aggregate([]);\n' * 200)
    analyzer.arrays = CountedArrays()
    result = analyzer.run()
    assert len(result.arrays) == 200 and not result.diagnostics
    assert analyzer.arrays.visits <= 800


def test_completion_preserves_existing_source():
    cases = [
        ('db.c.aggregate([{ "$ma|": {} }])', '$match', r'\$match'),
        ('db.c.aggregate([{ $ma|\n: {} }])', '$match', r'\$match'),
        ('db.c.aggregate([{ $ma|' + ' ' * 41 + ': {} }])', '$match', r'\$match'),
        ('db.c.fi|({x:1})', 'find', 'find'),
        ('db.c.find({a:{$g|t:1}})', '$gt', r'\$gt'),
        ('db.c.find({a:{$g|:1}})', '$gt', r'\$gt'),
        ('db.c.aggregate([{$group:{_id:null,n:{$co|}}}])', '$count', r'\$count: {}'),
        ('db.c.find({$text:{$|}})', '$search', r'\$search: "$0"'),
        ('db.c.aggregate([{$|}])', '$search', r'\$search: { $0 }'),
    ]
    for marked, label, expected in cases:
        offset = marked.index('|')
        text = marked.replace('|', '')
        item = next(c for c in features.completions(analyze(text), offset) if c.label == label)
        assert item.insert == expected, marked
        assert item.start == text.rfind('$', 0, offset) if label.startswith('$') else item.start == text.index('fi')
        if marked == 'db.c.find({a:{$g|t:1}})':
            assert text[:item.start] + item.insert.replace(r'\$', '$') + text[item.end:] == 'db.c.find({a:{$gt:1}})'


def test_completion_context_boundaries():
    assert complete('db.c.find({a:"db.c.fi|"})') == []
    assert '$match' in complete('db.c.aggregate([{$lookup:{from:"other",as:"joined",pipeline:[ | ]}}])')
    assert '$match' not in complete('db.c.updateOne({},[{$|}])')
    assert '$set' in complete('db.c.updateOne({},[{$|}])')
    labels = set(complete('db.c.updateOne({},{$addToSet:{a:{$each:[],$|}}})'))
    assert '$each' in labels and not labels.intersection({'$sort', '$slice', '$position'})
    assert '$push' not in complete('db.c.aggregate([{$project:{a:{$|}}}])')
    assert '$abs' not in complete('db.c.aggregate([{$group:{_id:null,a:{$|}}}])')


def test_optional_hover_enrichment_failure_is_contained():
    def fail(term):
        raise OSError('synthetic optional enrichment failure')
    assert features.hover_markdown('$match', fail) == features.hover_markdown('$match')



def test_lsp_positions_cover_line_endings_and_surrogates():
    pytest.importorskip('pygls')
    from lsprotocol import types as t

    from mdbx.mql import server as s
    for text in ('a\rb', 'a\nb', 'a\r\nb'):
        base = len(text) - 1
        assert s.offset_to_position(text, base) == t.Position(1, 0)
        assert s.position_to_offset(text, t.Position(1, 0)) == base
        assert s.position_to_offset(text, t.Position(0, 99)) == 1
    assert s.offset_to_position('\ud800x', 1) == t.Position(0, 1)
    assert s.position_to_offset('\ud800x', t.Position(0, 1)) == 1
    assert s.offset_to_position('😀x', 1) == t.Position(0, 2)
    assert s.position_to_offset('😀x', t.Position(0, 2)) == 1


def test_lsp_optimizer_requires_original_offsets_and_safe_logging(monkeypatch, caplog):
    pytest.importorskip('pygls')
    from types import SimpleNamespace as N

    from mdbx.mql import server as s
    monkeypatch.setenv('MDBX_LSP_OPTIMIZE', '1')
    finding = N(start=0, end=2, severity='medium', code='synthetic', pass_id='C1', message='synthetic', fix='x')
    monkeypatch.setattr(s, 'optimize', lambda *a, **k: N(original='different normalized text', findings=[finding]))
    assert s.optimizer_diagnostics('synthetic source') == []
    def fail(*a, **k):
        raise RuntimeError('SYNTHETIC_QUERY_LITERAL')
    monkeypatch.setattr(s, 'optimize', fail)
    with caplog.at_level('WARNING', logger='mql-lsp'):
        assert s.optimizer_diagnostics('synthetic input') == []
    assert caplog.records and 'SYNTHETIC_QUERY_LITERAL' not in caplog.text


def test_lsp_code_actions_revalidate_and_version_edits(monkeypatch):
    pytest.importorskip('pygls')
    from types import SimpleNamespace as N
    from unittest.mock import Mock

    from lsprotocol import types as t

    from mdbx.mql import server as s
    old = 'db.c.find({a:{$gtt:1}})'
    diagnostic = s.to_diagnostic(old, next(d for d in analyze(old).diagnostics if d.fix))
    handlers = {}
    fake = Mock()
    fake.feature.side_effect = lambda method, *args: lambda fn: handlers.setdefault(method, fn)
    doc = N(source=old, version=1)
    fake.workspace.get_text_document.return_value = doc
    monkeypatch.setattr(s, 'LanguageServer', lambda *a, **k: fake)
    monkeypatch.setattr(s, 'make_expertise_lookup', lambda: None)
    monkeypatch.setenv('MDBX_LSP_OPTIMIZE', '0')
    s.build_server()
    def actions(d):
        return handlers[t.TEXT_DOCUMENT_CODE_ACTION](t.CodeActionParams(
            text_document=t.TextDocumentIdentifier(uri='file:///synthetic.mql'), range=d.range,
            context=t.CodeActionContext(diagnostics=[d])))
    edits = actions(diagnostic)[0].edit.document_changes
    assert len(edits) == 1 and edits[0].text_document.version == 1
    assert edits[0].edits[0].new_text == '$gt' and edits[0].edits[0].range == diagnostic.range
    doc.source = old.replace('$gtt', 'live')
    doc.version = 2
    assert actions(diagnostic) == []
    for source, fix in [('mql', 7), ('other-linter', 'unowned')]:
        assert actions(t.Diagnostic(range=diagnostic.range, message='synthetic', source=source, data={'fix': fix})) == []


def test_lsp_optional_lookup_runtime_failure(monkeypatch, tmp_path):
    pytest.importorskip('pygls')
    import sqlite3
    from types import SimpleNamespace as N
    from unittest.mock import Mock

    import mdbx
    from mdbx.mql import server as s
    db = tmp_path / 'synthetic.sqlite'
    db.touch()
    monkeypatch.setattr(mdbx, 'index', N(default_db=lambda: db, connect=Mock(side_effect=sqlite3.OperationalError('synthetic'))), raising=False)
    monkeypatch.setattr(mdbx, 'search', N(keyword=Mock(side_effect=AssertionError('unexpected search'))), raising=False)
    lookup = s.make_expertise_lookup()
    assert lookup is not None and lookup('$match') == []
    mdbx.index.connect.assert_called_once_with(db)
    mdbx.search.keyword.assert_not_called()

def test_completion_long_suffix_uses_linear_prefix_scan(monkeypatch):
    # All completion regexes must be anchored full matches; suffix discovery scans backwards.
    def reject_search(*args, **kwargs):
        raise AssertionError("unanchored completion suffix search")
    monkeypatch.setattr(features.re, "search", reject_search)
    text = "identifier" * 10000 + "!"
    assert features.completions(analyze(""), 0) == []
    assert features.completions(analyze(text), len(text)) == []


def test_lsp_positions_reuse_snapshot_index():
    pytest.importorskip("pygls")
    from mdbx.mql import server as s
    text = "x\\n" * 1000
    s._positions.cache_clear()
    for offset in range(0, len(text), 2):
        s.offset_to_position(text, offset)
    assert s._positions.cache_info().misses == 1


def test_match_context_reaches_element_match_queries():
    text = 'db.c.aggregate([{$match:{items:{$elemMatch:{location:{$near:{}}}}}}])'
    assert any(d.code == "misplaced-operator" and "$match" in d.message for d in analyze(text).diagnostics)
