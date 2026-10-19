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
    rep = optimize("db.c.find({ t: { $gte: 5, $lte: 5 } })")
    assert rep.text == "db.c.find({ t: 5 })"


def test_expr_rule():
    assert "expr-unindexable" in codes('db.c.find({ $expr: { $gt: ["$a", "$b"] } })')
    assert "expr-unindexable" not in codes('db.c.find({ $expr: { $gt: ["$a", 5] } })')


def test_cursor_rules():
    c = codes("db.c.find({ a: 1 }).sort({ b: 1 }).skip(5000).batchSize(2).hint({ a: 1 })")
    assert {"deep-skip", "tiny-batch", "pinned-hint", "sort-no-limit"} <= c
    assert "legacy-count" in codes("db.c.count({ a: 1 })")
    rep = optimize("db.c.countDocuments({})")
    assert rep.text == "db.c.estimatedDocumentCount()"


def test_match_hoist_respects_produced_fields():
    src = "db.c.aggregate([{ $addFields: { d: 1 } }, { $sort: { t: 1 } }, { $match: { x: 1 } }])"
    rep = optimize(src)
    assert rep.text.startswith("db.c.aggregate([{ $match: { x: 1 } }, { $addFields")
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
    assert rec.shell() == "db.o.createIndex({ c: 1, s: -1, t: 1 })"
    assert "ERS" in rec.rationale and "PROJECTION_COVERED" in rec.rationale
    assert "add _id: 0" not in rec.rationale


def test_or_branch_indexes():
    rep = optimize("db.o.find({ $or: [{ a: 1 }, { b: 2 }] })")
    shells = {r.shell() for r in rep.indexes}
    assert {"db.o.createIndex({ a: 1 })", "db.o.createIndex({ b: 1 })"} <= shells


def test_lookup_index():
    rep = optimize('db.o.aggregate([{ $lookup: { from: "u", localField: "a", foreignField: "uid", as: "x" } }])')
    assert any(r.shell() == "db.u.createIndex({ uid: 1 })" for r in rep.indexes)


def test_lsp_diagnostics_and_toggle(monkeypatch):
    diags = optimizer_diagnostics("db.c.find({ name: /x/ })")
    assert any(d.code == "opt/unanchored-regex" and d.severity == "info" for d in diags)
    monkeypatch.setenv("MDBX_LSP_OPTIMIZE", "0")
    assert optimizer_diagnostics("db.c.find({ name: /x/ })") == []


def test_report_and_dict():
    rep = optimize((ROOT / "examples/slow-queries.mql").read_text())
    text = format_report(rep, "slow-queries.mql")
    assert "BLOCKING" in text and "Rewritten query" in text and "createIndex" in text
    d = to_dict(rep)
    # 5 queries in, 4 after the rewrite: estimatedDocumentCount() has no filter left to audit
    assert d["rewritten"] and d["iterations"] >= 2 and len(d["queries"]) == 4
    assert len(optimize(rep.original, apply=False).targets) == 5


def test_cli(tmp_path, capsys):
    f = tmp_path / "q.mql"
    f.write_text("db.c.find({ t: { $gte: 1, $lte: 1 } })")
    assert main(["optimize", str(f)]) == 0
    assert "Rewritten query" in capsys.readouterr().out
    assert main(["optimize", "--write", str(f)]) == 0
    assert f.read_text() == "db.c.find({ t: 1 })"
    f.write_text('db.c.find({ $where: "1" })')
    assert main(["opt", "--read-only", str(f)]) == 1


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
