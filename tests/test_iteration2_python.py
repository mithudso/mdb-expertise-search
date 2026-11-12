"""Synthetic gate1 regression contracts; no corpus, model, or service calls."""
import json

import pytest

from mdbx.mql import features
from mdbx.mql.analyze import analyze
from mdbx.mql.normalize import normalize
from mdbx.mql.optimize import IndexRec, format_report, optimize, to_dict
from mdbx.mql.parser import parse


@pytest.mark.parametrize("source", [
    'const pred={$gt:5}; db.c.find({$or:[{a:pred},{a:2}]})',
    'db.c.find({$or:[{a:value()},{a:2}]})',
    'const p="$a"; db.c.aggregate([{$unwind:{path:p}},{$match:{a:2}}])',
    'const p=[{$sort:{x:1}},{$match:{x:2}}]; p.splice(1,0,{$limit:1}); db.c.aggregate(p)',
    'db.c.aggregate([{$set:{a:nextValue()}},{$match:{b:nextValue()}}])',
])
def test_optimizer_does_not_apply_unproven_rewrites(source):
    assert not optimize(source).applied


def test_optimizer_literal_rewrites_and_rendering_stay_usable():
    report = optimize('db.c.find({$or:[{"a²":1},{"a²":2}]})')
    assert '"a²"' in report.text or '"a\\u00b2"' in report.text
    assert '["__proto__"]' in IndexRec('c', [('__proto__', 1)], '').shell()
    assert any(f.code == 'syntax' for f in optimize('db.c.find({a:1').findings)
    report = optimize('db.c.find({"\\u001b[2Jhidden":1})', apply=False)
    assert '\x1b' not in format_report(report)
    assert to_dict(report)['queries'][0]['line'] == 1
    pipe = optimize('db.c.aggregate([{$match:{$or:[{a:1},{b:2}]}}])', apply=False)
    assert {tuple(rec.keys) for rec in pipe.indexes} == {(('a',1),), (('b',1),)}
    assert 'May cover' not in optimize('db.c.find({a:null},{a:1,_id:0})', apply=False).indexes[0].rationale


@pytest.mark.parametrize('source', ['{}{}', '{a:1} {b:2}'])
def test_adjacent_statements_require_separator(source):
    assert parse(source)[1]
    assert normalize(source).kind == 'mongosh'


def test_literals_and_recovery_preserve_supported_input():
    assert not parse('\ufeffdb.c.find({a:"a\u2028b\u2029c"})')[1]
    assert parse('const x=`c${suffix}`')[0][0].node.kind == 'error'
    assert parse(r'const x=`c\${suffix}`')[0][0].node.kind == 'string'
    statements, errors = parse(r'const d={a:@/\}/,b:1};'+'\ndb.c.find(d)')
    assert errors and [prop.key for prop in statements[0].node.props] == ['a', 'b']
    for ending in ['\n', '\r', '\u2028', '\u2029']:
        assert parse('db.c.find({a:/x'+ending+'/})')[1]
        assert parse('db.c.find({a:/x\\'+ending+'/})')[1]
    text='const x={find:"c",filter:{a:1}}'
    assert normalize(text).text == text and normalize(text).kind == 'mongosh'
    source='{find:"c",filter:{r:/"/,s:`left\nright`}}'
    assert '`left\nright`' in normalize(source).text


@pytest.mark.parametrize('source,code', [
 ('db.c.find(db.d.updateOne({}, {a:1}))','update-shape'),
 ('db.c.aggregate([{$project:{x:{$map:[]}}}])','bad-argument'),
 ('db.c.aggregate([{$group:{_id:null,n:{$count:"x"}}}])','bad-argument'),
 ('db.c.find({a:{$slice:2}})','misplaced-operator'),
 ('db.c.find({a:{$not:{x:1}}})','bad-argument'),
 ('db.c.find({a:{$not:{$gt:1,x:2}}})','bad-argument'),
 ('db.c.aggregate([{$project:{x:{$accumulator:{}}}}])','misplaced-operator'),
 ('db.c.watch([{$changeStreamSplitLargeEvent:{}},{$match:{a:1}}])','stage-position'),
])
def test_contextual_analyzer_contracts(source,code):
    assert code in [d.code for d in analyze(source).diagnostics]


def test_analyzer_accepts_valid_contexts_and_separate_bindings():
    assert not analyze('db.c.find({}, {x:{$elemMatch:{a:{$gt:1}}}})').diagnostics
    assert not analyze('db.aggregate([{$documents:{$let:{vars:{},in:[]}}}])').diagnostics
    source='var d={a:1}; db.c.find(d); var d={$set:{a:1}}; db.c.updateOne({},d)'
    assert not analyze(source).diagnostics
    assert all('\x1b' not in d.message for d in analyze('db.c.find({"$\\u001b[2J":1})').diagnostics)


@pytest.mark.parametrize('source,label,offset', [
 ('db.c.aggregate([{ "$li" }])','$limit',22),
 ('db.c.find({a:{$gt /*c*/ : 1}})','$gt',16),
 ('db.c.fi /*c*/ ({})','find',7),
 ('db.c.find({}).so','sort',15),
 ('db["c"].fi','find',10),
 ('db.c.find({}).sort({a:{$m}})','$meta',25),
])
def test_completion_edits_remain_structural(source,label,offset):
    result=analyze(source)
    items=features.completions(result,offset)
    item=next(item for item in items if item.label==label)
    if label=='$limit':
        assert source[item.start:item.end]=='"$li"'
    if '/*c*/' in source:
        assert ': $0' not in item.insert and '($0)' not in item.insert


def test_completion_literal_and_sort_fields_guards():
    source='db.c.find({s:"db.c.fi'
    assert features.completions(analyze(source),len(source))==[]
    source='db.c.find({}).sort({$m:1})'
    assert '$meta' not in [c.label for c in features.completions(analyze(source),21)]
    assert 'accumulator: `object`' in features.hover_markdown('$count')


def test_lsp_plain_snippets_and_compact_positions():
    from mdbx.mql import server
    assert server._plain_snippet(r'\$limit: ${1:10}')=='$limit: 10'
    text='a\r\n😀x\ry\nz'
    for offset in [0,1,3,4,5,6,7,8,9]:
        pos=server.offset_to_position(text,offset)
        expected=offset if text[offset-1:offset+1]!='\r\n' else offset-1
        assert server.position_to_offset(text,pos)==expected
    starts,ends,astral=server._positions('x'*100000)
    assert len(starts)==1 and len(ends)==1 and not astral
    assert server._positions.cache_info().maxsize==1


def test_escape_heavy_provider_context_keeps_maximal_nonempty_prefix():
    from mdbx.providers import build_context
    from mdbx.search import Hit
    context,sources=build_context([Hit(1,'p','s','skill','h',1,'\\'*2000,1.0)],500)
    body=json.loads(context)['text']
    assert body and len(context)<=500 and len(sources)==1
    assert len(context)+2>500

@pytest.mark.parametrize("apply", [False, True])
def test_pipeline_or_indexes_keep_common_predicates_and_sort(apply):
    report = optimize('db.c.aggregate([{$match:{tenant:1,$or:[{a:1},{b:2}]}},{$sort:{createdAt:-1}}])', apply=apply)
    assert {tuple(rec.keys) for rec in report.indexes} == {
        (("tenant", 1), ("a", 1), ("createdAt", -1)),
        (("tenant", 1), ("b", 1), ("createdAt", -1)),
    }


def test_mcp_operator_context_contracts_and_recipe_description():
    from mdbx import mcp_server
    assert mcp_server.mql_operator("$size")["arguments"] == {"query": "nonneg", "expr": "any"}
    assert mcp_server.mql_operator("$count")["arguments"] == {"stage": "string", "acc": "object"}
    assert "recipe" in mcp_server.mdb_search.__doc__

def test_unknown_source_and_watch_indexes_remain_scoped():
    assert optimize("{a:1}").targets[0].collection is None
    assert not optimize("{a:1}").indexes
    report = optimize('[{$lookup:{from:"stores",localField:"store",foreignField:"storeId",as:"s"}}]')
    assert [rec.collection for rec in report.indexes] == ["stores"]
    assert report.indexes[0].rationale.startswith("$lookup from an unspecified collection probes stores.storeId")
    assert not optimize('db.c.watch([{$match:{"fullDocument.a":1}}])').indexes


@pytest.mark.parametrize("predicate", [
    "{a:null}", "{a:[1,2]}", "{a:{$eq:null}}", "{a:{$eq:[1,2]}}",
    "{$and:[{a:1},{a:{$elemMatch:{$gt:1}}}]}",
    "{$or:[{a:1},{a:{$not:{$eq:null}}}]}",
])
def test_known_fetch_requirements_suppress_covering_claim(predicate):
    report = optimize("db.c.find(" + predicate + ",{a:1,_id:0})", apply=False)
    assert report.indexes
    assert all("May cover" not in item.rationale for item in report.indexes)


def test_unknown_scalar_schema_keeps_conditional_coverage_advice():
    report = optimize("db.c.find({a:1},{a:1,_id:0})", apply=False)
    assert "May cover" in report.indexes[0].rationale
    assert "Confirm coverage with explain()" in report.indexes[0].rationale
