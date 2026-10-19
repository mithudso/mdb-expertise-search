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
    assert q.text.startswith('db.orders.find({"customerId":4711')
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
    assert n.queries[0].text.startswith("db.products.updateMany(")
    assert n.queries[0].evidence["durationMillis"] == 812  # millis renamed


def test_command_document_and_bare_inputs():
    assert normalize((FIX / "command-find.txt").read_text()).queries[0].text.startswith("db.users.find(")
    assert normalize((FIX / "bare-filter.txt").read_text()).kind == "filter"
    assert normalize((FIX / "bare-pipeline.txt").read_text()).queries[0].text.startswith("db.collection.aggregate([")
    assert normalize('{ aggregate: "my-coll", pipeline: [] }').queries[0].text == \
        'db.getCollection("my-coll").aggregate([])'


def test_other_commands():
    assert normalize('{ count: "c", query: { a: 1 } }').queries[0].text == "db.c.count({ a: 1 })"
    assert normalize('{ distinct: "c", key: "k", query: {} }').queries[0].text == 'db.c.distinct("k", {})'
    assert normalize('{ update: "c", updates: [{ q: { a: 1 }, u: { $set: { b: 2 } }, multi: true }] }') \
        .queries[0].text == "db.c.updateMany({ a: 1 }, { $set: { b: 2 } })"
    assert normalize('{ delete: "c", deletes: [{ q: { a: 1 }, limit: 1 }] }').queries[0].text == \
        "db.c.deleteOne({ a: 1 })"
    assert normalize('{ findAndModify: "c", query: { a: 1 }, sort: { t: 1 }, remove: true }').queries[0].text == \
        "db.c.findOneAndDelete({ a: 1 }, { sort: { t: 1 } })"


def test_ejson_wrappers_and_multiline_collapse():
    src = '{ find: "c", filter: { _id: { "$oid": "64b0c0ffee" },\n   n: { "$numberLong": "7" },\n   d: { "$date": { "$numberLong": "1700000000000" } } } }'
    q = normalize(src).queries[0].text
    assert q == 'db.c.find({ _id: ObjectId("64b0c0ffee"), n: 7, d: new Date(1700000000000) })'


def test_unrecognised_text_is_left_alone():
    for src in ["", "hello world", "[1, 2, 3]", "{}"]:
        n = normalize(src)
        assert n.kind == "mongosh" and not n.queries
        optimize(src)


def test_dict_carries_input_and_evidence():
    d = to_dict(optimize((FIX / "slowlog-find.txt").read_text()))
    assert d["input"]["kind"] == "log" and d["input"]["interpreted"].startswith("db.orders.find(")
    assert d["queries"][0]["evidence"]["docsExamined"] == 1843220
    assert to_dict(optimize("db.c.find({})"))["input"] == {"kind": "mongosh", "interpreted": None}


def test_goldens_are_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_optimizer_golden.py"), "--check"],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for g in FIX.glob("*.golden.json"):
        json.loads(g.read_text())
