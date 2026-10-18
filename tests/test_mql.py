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
