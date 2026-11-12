// Parity: the JavaScript optimizer must produce exactly what the Python reference produces for every
// input in tests/fixtures/optimizer/ (goldens written by scripts/gen_optimizer_golden.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";

import { formatReport, IndexRec, optimize, toDict } from "../lib/optimize.js";
import { normalize } from "../lib/normalize.js";
import { parse } from "../lib/parser.js";

const here = dirname(fileURLToPath(import.meta.url));
const FIX = join(here, "..", "..", "..", "tests", "fixtures", "optimizer");
const inputs = readdirSync(FIX).filter((f) => f.endsWith(".txt")).sort();

test("fixtures exist", () => {
  assert.ok(inputs.length >= 8, `expected fixtures in ${FIX}`);
});

for (const name of inputs) {
  const text = readFileSync(join(FIX, name), "utf8").replace(/\r\n?/g, "\n");
  const golden = JSON.parse(readFileSync(join(FIX, name.replace(/\.txt$/, ".golden.json")), "utf8"));

  test(`${name}: apply=true matches Python`, () => {
    assert.deepStrictEqual(toDict(optimize(text)), golden.apply);
  });

  test(`${name}: apply=false matches Python`, () => {
    assert.deepStrictEqual(toDict(optimize(text, { apply: false })), golden.read_only);
  });

  test(`${name}: text report matches Python`, () => {
    assert.equal(formatReport(optimize(text), name), golden.report);
  });
}

test("synthetic: automatic rewrites preserve query semantics and syntax", () => {
  const sources = [
    'db.c.countDocuments({}, {limit:1})',
    'db.c.find({a:{$gte:5,$lte:5}})',
    'const branch={b:1}; db.c.find({$or:[{a:1},{a:2},branch]})',
    'db.c.deleteMany({$or:[{a:1},false,{a:2}]})',
    'db.c.aggregate([{$project:{a:0}},{$match:{a:1}}])',
    'db.c.aggregate([{$project:{keep:1}},{$match:{a:1}}])',
    'const fields={a:0}; db.c.aggregate([{$set:fields},{$match:{a:1}}])',
    'db.c.aggregate([{$unset:fields},{$match:{a:1}}])',
    'db.c.aggregate([{$sort:{a:1}},{$match:{$and:branches}}])',
  ];
  for (const source of sources) assert.equal(optimize(source).text, source);
  const source = 'db.c.aggregate([{$sort:{a:1}},// keep comment\n  {$match:{b:1}}])';
  const report = optimize(source);
  assert.equal(report.text.split('db.c.aggregate(').length - 1, 1);
  assert.ok(report.text.includes('// keep comment\n'));
  assert.deepEqual(parse(report.text)[1], []);
  assert.equal(report.targets.length, 1);
});

test("synthetic: generated commands serialize keys and collection identity", () => {
  for (const key of ["a'b", 'a"b', 'x":1});__audit_marker=1;//', 'a\nb']) {
    assert.equal(new IndexRec('c', [[key,1]], '').shell(), 'db.getCollection("c").createIndex({ ' + JSON.stringify(key) + ': 1 })');
  }
  for (const collection of ['orders-2026', 'getCollection', 'c;__audit_marker=1;//']) {
    assert.equal(new IndexRec(collection, [['a',1]], '').shell(),
      'db.getCollection(' + JSON.stringify(collection) + ').createIndex({ a: 1 })');
  }
  const source = 'db.getCollection(name).find({a:1})';
  const report = optimize(source);
  assert.equal(report.text, source);
  assert.equal(report.targets[0].collection, null);
  assert.deepEqual(report.indexes, []);
});

test("synthetic: recommendations follow each binding and target", () => {
  let report = optimize('var f={a:1}; db.c.find(f); var f={b:1}; db.c.find(f);', { apply:false });
  assert.deepEqual(report.indexes.map((r) => r.keys), [[['a',1]],[['b',1]]]);
  report = optimize('const p=[{$match:{x:1}}]; db.a.aggregate(p); db.b.aggregate(p)', { apply:false });
  assert.deepEqual(report.indexes.map((r) => r.collection).sort(), ['a','b']);
  assert.deepEqual(optimize('db.c.find({$or:[{a:1},{a:2}]})', { apply:false }).indexes[0].keys, [['a',1]]);
  for (const [method,args] of [['findOneAndDelete','{tenant:1},{sort:{score:-1}}'],
    ['findOneAndReplace','{tenant:1},{x:2},{sort:{score:-1}}']]) {
    assert.deepEqual(optimize(`db.c.${method}(${args})`, { apply:false }).indexes[0].keys, [['tenant',1],['score',-1]]);
  }
});

test("synthetic: command batches, write methods and semantic options survive", () => {
  for (const [verb,key,extra,method] of [['update','updates',{u:{$set:{b:1}},upsert:true},'updateOne'],
    ['delete','deletes',{limit:{$numberInt:'1'}},'deleteOne']]) {
    const report = normalize(JSON.stringify({[verb]:'c',[key]:[1,2].map((a) => ({q:{a},...extra}))}));
    assert.equal(report.queries.length, 2);
    assert.equal(report.text.split('.' + method + '(').length - 1, 2);
    assert.ok(report.text.includes('"a":2'));
  }
  assert.ok(normalize('{find:"c",filter:{name:"a"},collation:{locale:"en",strength:2}}').text.includes('.collation({locale:"en",strength:2})'));
  assert.ok(normalize('{count:"c",query:{a:1},skip:2,limit:1}').text.includes('{skip: 2, limit: 1}'));
  for (const [source,method] of [['{update:"c",updates:[{q:{a:1},u:{b:2}}]}','replaceOne'],
    ['{op:"update",ns:"d.c",command:{q:{a:1},u:{b:2}}}','replaceOne'],
    ['{findAndModify:"c",query:{a:1},update:{b:2}}','findOneAndReplace']]) {
    assert.ok(normalize(source).text.includes('.' + method + '('));
  }
  assert.ok(normalize('{op:"remove",ns:"d.c",command:{q:{a:1},limit:{$numberInt:"1"}}}').text.includes('.deleteOne('));
  const batch = normalize('{attr:{command:{delete:"c",deletes:[{q:{a:1},limit:1},{q:{a:2},limit:1}]},docsExamined:100}}');
  assert.ok(batch.queries.every((q) => Object.keys(q.evidence).length === 0));
  for (const source of ['{find:"c",filter:{},tailable:true}',
    '{delete:"c",deletes:[{q:{a:1},limit:1},{q:{a:2},limit:2}]}']) assert.equal(normalize(source).text, source);
});

test("synthetic: wrappers remain data and preserve exact BSON values", () => {
  for (const [key,values] of [['$numberInt',['2147483648','-2147483649']],
    ['$numberLong',['9223372036854775808','-9223372036854775809','0, injected:1']],
    ['$numberDouble',['Infinity','NaN','1e309','0, injected:1']]]) {
    for (const value of values) assert.ok(normalize(JSON.stringify({find:'c',filter:{n:{[key]:value}}})).text.includes(JSON.stringify(value)));
  }
  assert.ok(normalize('{find:"c",filter:{n:{$numberLong:"9007199254740993"}}}').text.includes('NumberLong("9007199254740993")'));
  let report = normalize('{attr:{command:{find:"c",filter:{}},docsExamined:{$numberLong:"9007199254740993"}}}');
  assert.equal(report.queries[0].evidence.docsExamined, '9007199254740993');
  report = normalize('{attr:{command:{find:"c",filter:{}},docsExamined:{$numberDouble:"Infinity"},nreturned:1}}');
  assert.equal(report.queries[0].evidence.docsExamined, undefined);
});

test("synthetic: data strings and comments do not defeat normalization", () => {
  let report = normalize(JSON.stringify({attr:{command:{find:'c',filter:{note:'db.x.find('}},docsExamined:1000}}));
  assert.equal(report.kind, 'log');
  assert.equal(report.queries[0].evidence.docsExamined, 1000);
  report = normalize('{find:"c",filter:{a:1,// note\nb:2}}');
  const [statements,errors] = parse(report.text);
  assert.deepEqual(errors, []);
  assert.deepEqual(statements[0].node.items[0].props.map((p) => p.key), ['a','b']);
  assert.equal(normalize('{find:"getCollection",filter:{}}').text, 'db.getCollection("getCollection").find({})\n');
  for (const [source,kind] of [['{}','filter'],['[]','pipeline']]) assert.equal(normalize(source).kind, kind);
});

test("synthetic: advice accounts for expressions, regex alternation, and field limits", () => {
  for (const [source,code] of [['db.c.find({$expr:{$eq:["$a",{$add:["$b",1]}]}})','expr-unindexable'],
    ['db.c.find({x:/^a|b/})','unanchored-regex'],['db.c.find({x:/^a/m})','unanchored-regex']]) {
    assert.ok(optimize(source).findings.some((f) => f.code === code));
  }
  const negation = optimize('db.c.find({a:{$ne:null}})').findings.find((f) => f.code === 'negation');
  assert.doesNotMatch(negation.message, /matches documents missing the field/);
  const regex = optimize('db.c.find({a:/^abc/i})').findings.find((f) => f.code === 'case-insensitive-regex');
  assert.match(regex.message, /not collation-aware/);
  const source = 'db.c.find({' + Array.from({length:33}, (_,i) => `k${i}:${i}`).join(',') + '})';
  const report = optimize(source, { apply:false });
  assert.deepEqual(report.indexes, []);
  assert.ok(report.findings.some((f) => f.code === 'index-too-wide'));
});

test("synthetic: evidence identity and position lookup survive source edits", (t) => {
  const source = '{attr:{command:{find:"a",filter:{$or:[{a:1},{a:2}]}},planSummary:"COLLSCAN"}}\n{attr:{command:{find:"b",filter:{b:1}},planSummary:"IXSCAN"}}';
  const report = optimize(source);
  assert.ok(report.applied.length);
  assert.deepEqual(toDict(report).queries.map((q) => q.evidence.planSummary), ['COLLSCAN','IXSCAN']);
  const n = 200;
  const many = optimize('db.c.find({a:{$ne:1}});\n'.repeat(n), { apply:false });
  let visits = 0;
  const original = String.prototype.charCodeAt;
  const spy = t.mock.method(String.prototype, 'charCodeAt', function(i) { visits++; return original.call(this,i); });
  try {
    const output = toDict(many);
    assert.equal(output.queries[n-1].line, n);
    assert.ok(visits <= 2 * many.text.length);
  } finally { spy.mock.restore(); }
});

test("synthetic: fixture loading normalizes CRLF and CR inputs", () => {
  const root = mkdtempSync(join(tmpdir(), 'mdbx-parity-newlines-'));
  try {
    const target = join(root, 'editors/chrome/test/parity.test.mjs');
    const lib = join(root, 'editors/chrome/lib');
    const fixture = join(root, 'tests/fixtures/optimizer');
    for (const path of [dirname(target), lib, fixture]) mkdirSync(path, { recursive:true });
    writeFileSync(join(root, 'package.json'), JSON.stringify({ type:'module' }));
    copyFileSync(fileURLToPath(import.meta.url), target);
    writeFileSync(join(lib, 'optimize.js'), 'export const optimize=text=>({text}); export const toDict=value=>value; export const formatReport=()=>""; export class IndexRec {}');
    writeFileSync(join(lib, 'normalize.js'), 'export const normalize=()=>{};');
    writeFileSync(join(lib, 'parser.js'), 'export const parse=()=>{};');
    const text = '// synthetic\ndb.c.find({a:1});\n';
    for (let i=0; i<8; i++) {
      const base = join(fixture, String(i));
      writeFileSync(base + '.txt', text.replaceAll('\n', i % 2 ? '\r' : '\r\n'));
      writeFileSync(base + '.golden.json', JSON.stringify({ apply:{text}, read_only:{text}, report:'' }));
    }
    const result = spawnSync(process.execPath, ['--test', '--test-name-pattern',
      'fixtures exist|matches Python', target], { cwd:root, encoding:'utf8', timeout:10000 });
    assert.equal(result.status, 0, result.error?.message ?? result.stdout + result.stderr);
  } finally { rmSync(root, { recursive:true, force:true }); }
});
