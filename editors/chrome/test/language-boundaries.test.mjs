import {countedSource} from "./counted-source.mjs";
import { test } from "node:test";
import assert from "node:assert/strict";
import {parse} from "../lib/parser.js";
import {analyze} from "../lib/analyze.js";
import {normalize} from "../lib/normalize.js";
import {optimize} from "../lib/optimize.js";
function observe(id, run) { test(id, () => { const result = run(); assert.equal(result.satisfied, true, JSON.stringify(result.observed)); }); }
observe("parser-template", () => {
  const quote=String.fromCharCode(96), dynamic="$"+"{suffix}";
  const source="{find:"+quote+"c"+dynamic+quote+",filter:{a:1}}";
  const normalized=normalize(source);
  const result=optimize("db.getCollection("+quote+"c"+dynamic+quote+").find({a:1})",{apply:false});
  const observed={kind:parse(quote+"c"+dynamic+quote)[0][0].node.kind, normalized:normalized.text,
                  collection:normalized.queries[0]?.collection, indexes:result.indexes.map(index=>index.collection)};
  return {observed, satisfied:observed.kind!=="string" && normalized.text===source && normalized.changed===false && normalized.queries.length===0 && result.targets.length===1 && result.targets[0].collection===null && result.indexes.length===0};
});
observe("parser-unsafe-integer", () => {
  const result=normalize('{attr:{command:{find:"c",filter:{}},docsExamined:9007199254740993,nreturned:1}}');
  const value=result.queries[0].evidence.docsExamined;
  return {observed:{value,type:typeof value},satisfied:value==="9007199254740993"};
});
observe("parser-regex-recovery", () => {
  const result=parse("const d={a:@/}/,b:1};\ndb.c.find(d)");
  const keys=result[0][0].node.props.map(prop=>prop.key);
  return {observed:{keys,errors:result[1].length},satisfied:result[1].length>0 && keys.join(",")==="a,b"};
});
observe("parser-regex-newlines", () => {
  const cases=["\r","\u2028","\u2029","\\\n"].map(separator=>{
    const source="{a:/x"+separator+"y/}";
    return {separator:Array.from(separator,c=>c.codePointAt(0)),errors:parse(source)[1].length,
            preserved:normalize(source).text===source};
  });
  return {observed:cases,satisfied:cases.every(item=>item.errors>0 && item.preserved)};
});
function unicodeWork(count) {
  const source='"'+"\\u{".repeat(count)+'"';
  let scans=0;
  parse(countedSource(source,n=>{scans+=n;}));
  return {count,scans};
}
observe("parser-braced-unicode-complexity", () => {
  const small=unicodeWork(500),large=unicodeWork(1000);
  return {observed:{small,large,ratio:large.scans/small.scans},satisfied:small.scans>0 && large.scans<=3*small.scans+100};
});
observe("analyze-find-projection", () => {
  const source="db.c.find({}, "+JSON.stringify({items:{$elemMatch:{score:{$exists:true}}}})+")";
  const diagnostics=analyze(source).diagnostics;
  return {observed:diagnostics.map(diag=>({code:diag.code,message:diag.message})),satisfied:diagnostics.length===0};
});
observe("analyze-int64-max", () => {
  const diagnostics=analyze("db.c.aggregate([{$limit:9223372036854775807}])").diagnostics;
  return {observed:diagnostics.map(diag=>({code:diag.code,message:diag.message})),satisfied:diagnostics.length===0};
});
observe("analyze-map-contract", () => {
  const diagnostics=analyze("db.c.aggregate([{$project:{x:{$map:42}}}])").diagnostics;
  return {observed:diagnostics,satisfied:diagnostics.some(diag=>diag.code==="bad-argument")};
});
function symbolWork(count) {
  const original=Map.prototype.set,has=Set.prototype.has;
  let comparisons=0;
  Map.prototype.set=function(key,value){
    if(key?.kind==='array' && Array.isArray(value) && value[0]?.kind==='stage') value=new Proxy(value.map(symbol=>new Proxy(symbol,{get(target,property,receiver){
      if(['start','end','kind'].includes(property)) comparisons++;
      return Reflect.get(target,property,receiver);
    }})),{get(target,property,receiver){if(typeof property==='string' && /^[0-9]+$/.test(property)) comparisons++;return Reflect.get(target,property,receiver);}});
    return Reflect.apply(original,this,[key,value]);
  };
  Set.prototype.has=function(value){if(value?.kind==='stage')comparisons++;return Reflect.apply(has,this,[value]);};
  try {analyze("db.c.aggregate(["+Array(count).fill('{$lookup:{from:"other",as:"joined",pipeline:[]}}').join(",")+"])");}
  finally {Map.prototype.set=original;Set.prototype.has=has;}
  return {count,comparisons};
}
observe("analyze-symbol-complexity", () => {
  const small=symbolWork(200),large=symbolWork(400);
  return {observed:{small,large,ratio:large.comparisons/small.comparisons},satisfied:small.comparisons>0 && large.comparisons<=3*small.comparisons+100};
});
observe("analyze-wide-symbols", () => {
  const count=200000;
  try {
    const result=analyze("db.c.aggregate(["+Array(count).fill("{$limit:1}").join(",")+"])");
    return {observed:{count,symbols:result.symbols[0].children.length},satisfied:result.symbols.length===1 && result.symbols[0].children.length===count};
  } catch(error) {
    return {observed:{count,error:error.name,message:error.message},satisfied:false};
  }
});


test('paired parser: adjacent expressions need a statement separator',()=>{
  for(const source of ['{}{}','{a:1} {b:2}']){
    assert.ok(parse(source)[1].some(error=>error.message==='expected a statement separator'));
    assert.equal(normalize(source).text,source);
  }
  assert.deepEqual(parse('{a:1}\n{b:2}')[1],[]);
});

test('paired parser: modern string literals retain Unicode line separators',()=>{
  for(const separator of ['\u2028','\u2029']){
    const source='"left'+separator+'right"';
    const [statements,errors]=parse(source);
    assert.deepEqual(errors,[]);
    assert.equal(statements[0].node.value,'left'+separator+'right');
  }
});


test('paired lint preservation: documents rejects plain objects and keeps array expressions',()=>{
  for(const value of ['{}','{a:1}','{$literal:[],a:1}']){
    const diagnostics=analyze('db.c.aggregate([{$documents:'+value+'}])').diagnostics;
    assert.ok(diagnostics.some(d=>d.code==='bad-argument' && d.message==='$documents expects an array, got object.'));
  }
  for(const value of ['[]','[{a:1}]','{$literal:[]}','{$concatArrays:[[],[]]}']){
    assert.deepEqual(analyze('db.c.aggregate([{$documents:'+value+'}])').diagnostics,[]);
  }
});

test('paired lint preservation: adjacent JSON is rejected while shell and log headers stay tolerant',()=>{
  for(const source of ['{}{}','[] []']){
    assert.ok(parse(source)[1].some(d=>d.message==='expected a statement separator'));
    assert.equal(normalize(source).text,source);
  }
  assert.deepEqual(parse('show collections')[1],[]);
  const source='slow query details\n{attr:{command:{find:"c",filter:{}}}}';
  assert.deepEqual(parse(source)[1],[]);
  assert.equal(normalize(source).queries.length,1);
});
