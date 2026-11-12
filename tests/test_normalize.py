import json
import subprocess
import sys
from pathlib import Path

from mdbx.mql.normalize import normalize
from mdbx.mql.optimize import optimize, to_dict

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "optimizer"


def codes(src: str) -> set[str]:
    return {f.code for f in optimize(src, apply=False).findings}


def test_mongosh_passthrough():
    for src in ["db.c.find({ a: 1 })", 'db.getCollection("x").aggregate([])', 'db["my-c"].find({})']:
        n = normalize(src)
        assert n.kind == "mongosh" and n.text == src


def test_slow_log_line_find():
    n = normalize((FIX / "slowlog-find.txt").read_text())
    assert n.kind == "log" and len(n.queries) == 1
    q = n.queries[0]
    assert q.collection == "orders"
    assert q.text.startswith('db.getCollection("orders").find({"customerId":4711')
    assert 'ISODate("2026-01-01T00:00:00.000Z")' in q.text  # $date unwrapped
    assert ".sort(" in q.text and ".skip(2000)" in q.text and ".limit(20)" in q.text
    assert "lsid" not in q.text and "$db" not in q.text
    assert q.evidence["planSummary"] == "COLLSCAN" and q.evidence["maxTimeMS"] == 5000
    c = codes((FIX / "slowlog-find.txt").read_text())
    assert {"log-collscan", "log-scan-ratio", "log-blocking-sort", "log-spill", "log-timeout-bound"} <= c


def test_getmore_uses_originating_command_and_multiple_lines():
    n = normalize((FIX / "slowlog-multi.txt").read_text())
    assert [q.collection for q in n.queries] == ["events", "orders"]
    assert n.queries[1].text.endswith(".batchSize(2)")
    assert n.queries[0].evidence["replanned"] is True
    assert "log-replanned" in codes((FIX / "slowlog-multi.txt").read_text())


def test_profiler_write_entry():
    n = normalize((FIX / "profiler-update.txt").read_text())
    assert n.kind == "profile"
    assert n.queries[0].text.startswith('db.getCollection("products").updateMany(')
    assert n.queries[0].evidence["durationMillis"] == 812  # millis renamed


def test_command_document_and_bare_inputs():
    assert normalize((FIX / "command-find.txt").read_text()).queries[0].text.startswith('db.getCollection("users").find(')
    assert normalize((FIX / "bare-filter.txt").read_text()).kind == "filter"
    assert normalize((FIX / "bare-pipeline.txt").read_text()).queries[0].text.startswith("db.collection.aggregate([")
    assert normalize('{ aggregate: "my-coll", pipeline: [] }').queries[0].text == \
        'db.getCollection("my-coll").aggregate([])'


def test_other_commands():
    assert normalize('{ count: "c", query: { a: 1 } }').queries[0].text == 'db.getCollection("c").count({ a: 1 })'
    assert normalize('{ distinct: "c", key: "k", query: {} }').queries[0].text == 'db.getCollection("c").distinct("k", {})'
    assert normalize('{ update: "c", updates: [{ q: { a: 1 }, u: { $set: { b: 2 } }, multi: true }] }') \
        .queries[0].text == 'db.getCollection("c").updateMany({ a: 1 }, { $set: { b: 2 } })'
    assert normalize('{ delete: "c", deletes: [{ q: { a: 1 }, limit: 1 }] }').queries[0].text == \
        'db.getCollection("c").deleteOne({ a: 1 })'
    assert normalize('{ findAndModify: "c", query: { a: 1 }, sort: { t: 1 }, remove: true }').queries[0].text == \
        'db.getCollection("c").findOneAndDelete({ a: 1 }, { sort: { t: 1 } })'


def test_ejson_wrappers_and_multiline_collapse():
    src = '{ find: "c", filter: { _id: { "$oid": "64b0c0ffee" },\n   n: { "$numberLong": "7" },\n   d: { "$date": { "$numberLong": "1700000000000" } } } }'
    q = normalize(src).queries[0].text
    assert q == 'db.getCollection("c").find({ _id: ObjectId("64b0c0ffee"), n: NumberLong("7"), d: new Date(1700000000000) })'


def test_unrecognised_text_is_left_alone():
    for src in ["", "hello world", "[1, 2, 3]"]:
        n = normalize(src)
        assert n.kind == "mongosh" and not n.queries and n.text == src
        report = optimize(src)
        assert report.original == report.text == src


def test_dict_carries_input_and_evidence():
    d = to_dict(optimize((FIX / "slowlog-find.txt").read_text()))
    assert d["input"]["kind"] == "log" and d["input"]["interpreted"].startswith('db.getCollection("orders").find(')
    assert d["queries"][0]["evidence"]["docsExamined"] == 1843220
    assert to_dict(optimize("db.c.find({})"))["input"] == {"kind": "mongosh", "interpreted": None}


def test_goldens_are_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_optimizer_golden.py"), "--check"],
                       check=False, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    for g in FIX.glob("*.golden.json"):
        json.loads(g.read_text())


# Synthetic command/literal regressions. No service or model calls.
def test_numeric_wrappers_remain_data_and_exact():
    from mdbx.mql.parser import parse
    source = json.dumps({'find':'c', 'filter':{'n':{'$numberLong':'0, injected: 1'}}})
    normalized = normalize(source)
    statements, errors = parse(normalized.text)
    assert not errors
    assert [p.key for p in statements[0].node.items[0].props] == ['n']
    assert 'NumberLong("9007199254740993")' in normalize('{find:"c",filter:{n:{$numberLong:"9007199254740993"}}}').text
    source = '{attr:{command:{find:"c",filter:{}},docsExamined:{$numberLong:"9007199254740993"}}}'
    assert normalize(source).queries[0].evidence['docsExamined'] == '9007199254740993'
    source = '{attr:{command:{find:"c",filter:{}},docsExamined:{$numberDouble:"Infinity"},nreturned:1}}'
    assert 'docsExamined' not in normalize(source).queries[0].evidence


def test_every_batch_statement_and_semantic_options_survive():
    for verb, key, extra, method in [('update','updates',{'u':{'$set':{'b':1}},'upsert':True},'updateOne'),
                                     ('delete','deletes',{'limit':{'$numberInt':'1'}},'deleteOne')]:
        source = json.dumps({verb:'c',key:[dict(q={'a':a},**extra) for a in (1,2)]})
        normalized = normalize(source)
        assert len(normalized.queries) == 2 and normalized.text.count('.'+method+'(') == 2
        assert '"a": 2' in normalized.text
    assert '.collation({locale:"en",strength:2})' in normalize('{find:"c",filter:{name:"a"},collation:{locale:"en",strength:2}}').text
    assert '{skip: 2, limit: 1}' in normalize('{count:"c",query:{a:1},skip:2,limit:1}').text
    assert '{upsert: true}' in normalize('{update:"c",updates:[{q:{a:1},u:{$set:{b:2}},upsert:true}]}').text
    source = '{attr:{command:{delete:"c",deletes:[{q:{a:1},limit:1},{q:{a:2},limit:1}]},docsExamined:100}}'
    assert all(not q.evidence for q in normalize(source).queries)
    source = '{delete:"c",deletes:[{q:{a:1},limit:2}]}'
    assert normalize(source).text == source


def test_replacement_methods_and_wrapped_delete_limit():
    for source in ['{update:"c",updates:[{q:{a:1},u:{b:2}}]}', '{op:"update",ns:"d.c",command:{q:{a:1},u:{b:2}}}']:
        assert normalize(source).queries[0].text == 'db.getCollection("c").replaceOne({a:1}, {b:2})'
    assert normalize('{findAndModify:"c",query:{a:1},update:{b:2}}').queries[0].text == 'db.getCollection("c").findOneAndReplace({a:1}, {b:2})'
    source = '{op:"remove",ns:"d.c",command:{q:{a:1},limit:{$numberInt:"1"}}}'
    assert '.deleteOne(' in normalize(source).text


def test_normalization_ignores_mongosh_in_data_and_preserves_comments():
    from mdbx.mql.parser import parse
    source = json.dumps({'attr':{'command':{'find':'c','filter':{'note':'db.x.find('}},'docsExamined':1000}})
    normalized = normalize(source)
    assert normalized.kind == 'log' and normalized.queries[0].evidence['docsExamined'] == 1000
    source = '{find:"c",filter:{a:1,// note\nb:2}}'
    statements, errors = parse(normalize(source).text)
    assert not errors and [p.key for p in statements[0].node.items[0].props] == ['a','b']
    assert normalize('{find:"getCollection",filter:{}}').text == 'db.getCollection("getCollection").find({})\n'
    for source, kind in [('{}','filter'),('[]','pipeline')]:
        assert normalize(source).kind == kind


def test_wrapper_ranges_and_unsupported_commands_preserve_source():
    for key, values in [('$numberInt', ['2147483648', '-2147483649']),
                        ('$numberLong', ['9223372036854775808', '-9223372036854775809', '1;injected()']),
                        ('$numberDouble', ['Infinity', 'NaN', '1e309', '0, injected:1'])]:
        for value in values:
            source = json.dumps({'find':'c','filter':{'n':{key:value}}})
            assert json.dumps(value) in normalize(source).text
    for source in ['{find:"c",filter:{},tailable:true}',
                   '{update:"c",updates:[{q:{a:1},u:{b:2},multi:true}]}',
                   '{delete:"c",deletes:[{q:{a:1},limit:1},{q:{a:2},limit:2}]}',
                   '{find:"c",filter:{a:1}}; unsupported']:
        assert normalize(source).text == source
    # The old preparse probe scanned the remaining suffix for every unmatched db[ prefix.
    source = 'db[' * 2000
    assert normalize(source).text == source
