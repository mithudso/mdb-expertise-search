import json
from pathlib import Path

import pytest

from mdbx.mql import features, operators
from mdbx.mql.analyze import analyze
from mdbx.mql.normalize import normalize
from mdbx.mql.optimize import format_report, optimize, to_dict
from mdbx.mql.parser import parse


@pytest.mark.parametrize(
    "source",
    [
        "db.c.aggregate([{$project:{_id:{$literal:1},a:0}}])",
        "db.c.updateOne({},{$pull:{items:{score:{$in:1}}}})",
        "db.c.aggregate([{$setWindowFields:{sortBy:{t:1},output:{r:{$rank:1}}}}])",
        "db.c.find({$text:{$search:7,$language:[],$caseSensitive:1}})",
        "db.c.updateOne({},{$push:{items:{$each:[1],$position:1.5,$slice:1.5}}})",
        "db.c.aggregate([{$documents:42}])",
        "db.c.aggregate([{$project:{a:{$eq:[1]},b:{$in:[1]}}}])",
    ],
)
def test_reject_invalid_contextual_contracts(source):
    assert any(d.code in {"bad-argument", "projection-mix"} for d in analyze(source).diagnostics)


@pytest.mark.parametrize(
    "source",
    [
        "db.c.find({}, {scores:{$elemMatch:{$gte:80}}})",
        "db.c.aggregate([{$project:{a:{$and:[]},b:{$or:[]}}}])",
        "db.c.find({a:{$eq:[1]},b:{$in:[1,2,3]}})",
    ],
)
def test_accept_valid_contextual_contracts(source):
    assert not analyze(source).diagnostics


def test_update_metadata_and_text_hover():
    for name in ("$push", "$addToSet", "$min", "$max"):
        assert operators.get(name).arg_for("update") == "object"
        assert operators.get(name).arg_for("accexpr") == "any"
    assert "text: `string`" in features.hover_markdown("$search")


def test_completion_active_property_and_regex_guard():
    text = "db.c.find({a:, $})"
    offset = text.index("$") + 1
    assert features.completions(analyze(text), offset)
    text = "db.c.find({a:/$$/})"
    offset = text.index("$$") + 2
    assert features.completions(analyze(text), offset) == []


@pytest.mark.parametrize(
    "source",
    [
        "db.c.find({$or:[{a:1},{a:2}],$or:[{b:3},{b:4}]})",
        "const f={$or:[{a:1},{a:2}]}; db.c.find(f); db.c.replaceOne({_id:1},f)",
        "const f={$or:[{a:1},{a:2}]}; db.c.find(f); other.find(f)",
        "var p=[{$sort:{x:1}},{$match:{y:1}}]; capture(p); db.c.aggregate(p); var p=[];",
        "const q={$or:[{a:1},{a:2}]}; db.c.find(q); lookup[q.$or];",
    ],
)
def test_unsafe_declaration_or_overwritten_predicate_preserves_source(source):
    assert optimize(source).text == source


def test_literal_declaration_still_rewrites():
    report = optimize("const f={$or:[{a:1},{a:2}]};db.c.find(f)")
    assert [f.code for f in report.applied] == ["or-to-in"]
    assert "$in: [1, 2]" in report.text


def test_rand_is_not_constant_and_regex_in_is_range():
    assert any(
        f.code == "expr-unindexable"
        for f in optimize('db.c.find({$expr:{$lt:["$score",{$rand:{}}]}})', apply=False).findings
    )
    report = optimize("db.c.find({name:{$in:[/^A/]}}).sort({createdAt:1})", apply=False)
    assert report.indexes[0].keys[0] == ("createdAt", 1)
    assert "SORT_MERGE" not in report.indexes[0].rationale


def test_report_summary_and_line_boundaries():
    report = optimize("db.c.aggregate([{$set:{a:1}},{$match:{b:1}}])", apply=False)
    assert "1 medium" in format_report(report).splitlines()[0]
    for sep in ("\r", "\u2028", "\u2029", "\r\n"):
        report = optimize("db.c.find({a:1});" + sep + "db.c.find({b:{$ne:1}})", apply=False)
        assert next(f for f in to_dict(report)["findings"] if f["code"] == "negation")["line"] == 2


def test_surrogate_reporting_is_utf8_serializable():
    source = 'db.c.find({"$\\ud800":1,"\\ud800":{$ne:1}})'
    for d in analyze(source).diagnostics:
        d.message.encode("utf8")
    format_report(optimize(source, apply=False)).encode("utf8")


@pytest.mark.parametrize(
    "source",
    [
        "db[].find({a:1})",
        "db[/*empty*/].find({a:1})",
        "db.c.find({}) db.c.countDocuments({})",
        "1e",
        "{a:1\u0662}",
        "db.c.find({r:/a/z})",
        "/a/ii",
        "/a/uv",
    ],
)
def test_invalid_javascript_reports_syntax(source):
    assert parse(source)[1]


def test_computed_children_and_template_cooking():
    source = "lookup[`left\nright`]"
    assert any(
        n.kind == "string" and n.value == "left\nright" for n in parse(source)[0][0].node.walk()
    )
    text = '{find:"c",filter:{a:' + source + "}}"
    assert "`left\nright`" in normalize(text).text
    for sep in ("\r", "\r\n"):
        assert normalize("{find:`c" + sep + "x`,filter:{}}").queries[0].collection == "c\nx"
    assert parse("`c\\rx`")[0][0].node.value == "c\rx"
    assert [p.key for p in parse("{1.0:1,1:2}")[0][0].node.props] == ["1", "1"]


def test_numeric_evidence_policies_match_encodings():
    prefix = '{attr:{command:{find:"c",filter:{}},nreturned:1,docsExamined:'
    a = normalize(prefix + "1e20}}").queries[0].evidence
    b = normalize(prefix + '{$numberDouble:"1e20"}}}').queries[0].evidence
    assert a == b and type(a["docsExamined"]) is type(b["docsExamined"])
    digits = "1" + "0" * 309
    assert normalize(prefix + digits + "}}").queries[0].evidence["docsExamined"] == digits


def test_regex_recovery_has_linear_source_reads():
    class Watched(str):
        reads = 0

        def __getitem__(self, key):
            if isinstance(key, int):
                self.reads += 1
            return super().__getitem__(key)

    counts = []
    for n in (256, 512):
        source = Watched("{a:@" + "/[" * n + "}")
        parse(source)
        counts.append(source.reads)
    assert counts[0] > 0 and counts[1] <= 3 * counts[0] + 100


def test_plain_choice_snippets():
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from mdbx.mql.server import _plain_snippet

    assert _plain_snippet(r"\$sort: { ${1:field}: ${2|1,-1|} }") == "$sort: { field: 1 }"


def test_empty_code_actions_do_no_analysis(monkeypatch):
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from types import SimpleNamespace as N
    from unittest.mock import Mock

    from lsprotocol import types as t

    from mdbx.mql import server as s

    handlers = {}
    fake = Mock()
    fake.feature.side_effect = lambda method, *args: lambda fn: handlers.setdefault(method, fn)
    monkeypatch.setattr(s, "LanguageServer", lambda *a, **k: fake)
    monkeypatch.setattr(s, "make_expertise_lookup", lambda: None)
    s.build_server()
    scan = Mock(side_effect=AssertionError("empty action should not analyze"))
    monkeypatch.setattr(s, "analyze", scan)
    params = N(context=N(diagnostics=[]))
    assert handlers[t.TEXT_DOCUMENT_CODE_ACTION](params) == []
    scan.assert_not_called()


def test_atomic_generator_outputs_preserve_existing_bytes(monkeypatch, tmp_path):
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    for name in ("gen_chrome_operators", "gen_lint_golden", "gen_optimizer_golden"):
        spec = importlib.util.spec_from_file_location(name, root / "scripts" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = tmp_path / (name + ".output")
        target.write_bytes(b"previous-valid-output")
        with monkeypatch.context() as patch:
            patch.setattr(
                module.os,
                "replace",
                lambda *args: (_ for _ in ()).throw(OSError("synthetic disk failure")),
            )
            with pytest.raises(OSError):
                module._atomic_write(target, b"new-output")
        assert target.read_bytes() == b"previous-valid-output"
        assert not list(tmp_path.glob("." + target.name + ".*"))


def test_optional_hover_uses_read_only_connection(monkeypatch, tmp_path):
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    import sqlite3
    from types import SimpleNamespace as N
    from unittest.mock import Mock

    import mdbx
    from mdbx.mql import server

    db = tmp_path / "synthetic.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table synthetic(value)")
    con.commit()
    con.execute("begin immediate")
    blocked = Mock(side_effect=AssertionError("schema connector must not be used"))
    search = Mock(return_value=[])
    monkeypatch.setattr(mdbx, "index", N(default_db=lambda: db, connect=blocked), raising=False)
    monkeypatch.setattr(mdbx, "search", N(keyword=search), raising=False)
    try:
        lookup = server.make_expertise_lookup()
        assert lookup("$match") == []
    finally:
        con.close()
    blocked.assert_not_called()
    search.assert_called_once()


def test_constant_wrappers_keep_literal_semantics():
    for operator in ("$literal", "$const"):
        source = 'db.c.find({$expr:{$eq:["$score",{' + operator + ":{$rand:{}}}]}})"
        assert not any(f.code == "expr-unindexable" for f in optimize(source, apply=False).findings)


def test_unique_field_collection_has_linear_hash_and_equality_work():
    from mdbx.mql.optimize import _uniq

    class Field(str):
        work = 0

        def __hash__(self):
            type(self).work += 1
            return super().__hash__()

        def __eq__(self, other):
            type(self).work += 1
            return super().__eq__(other)

    values = [Field(str(i)) for i in range(1024)]
    result = _uniq(values)
    assert result == values and 0 < Field.work <= 4 * len(values)


def test_generator_terminal_names_and_surrogate_serialization(monkeypatch, tmp_path, capsys):
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "names_generator", root / "scripts/gen_optimizer_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / ("\x1b[2J.txt")
    source.write_text("{a:1}")
    monkeypatch.setattr(module, "FIXTURES", tmp_path)
    monkeypatch.setattr(sys, "argv", ["generator", "--check", "--print"])
    assert module.main() == 1
    output = capsys.readouterr().out
    assert "\x1b" not in output and r"\x1b" in output
    spec = importlib.util.spec_from_file_location(
        "surrogate_generator", root / "scripts/gen_lint_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        module, "lint_dict", lambda text: {"diagnostics": [{"message": "\ud800"}], "symbols": []}
    )
    encoded = module.golden(source).encode("utf8")
    assert json.loads(encoded)["diagnostics"][0]["message"] == "\ud800"
