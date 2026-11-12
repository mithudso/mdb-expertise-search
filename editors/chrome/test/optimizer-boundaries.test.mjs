import {test} from 'node:test';
import assert from 'node:assert/strict';
import {optimize,toDict,formatReport} from '../lib/optimize.js';
import {parse} from '../lib/parser.js';

test('regression O1: unresolved unwind path and output name block result-changing hoists',()=>{
  for(const source of [
    'const path="$items"; db.c.aggregate([{$unwind:{path:path}},{$match:{items:{$gt:1}}}])',
    'const output="index"; db.c.aggregate([{$unwind:{path:"$items",includeArrayIndex:output}},{$match:{index:0}}])'
  ]) assert.equal(optimize(source).text,source);
});

test('regression O2: duplicate source properties do not become additional active predicates',()=>{
  const source='db.c.find({$or:[{a:1},{a:2}],$or:[{b:3},{b:4}]})';
  assert.deepEqual(parse(source)[1],[]);
  assert.equal(optimize(source).text,source);
});

test('regression O3: unresolved equality operands cannot become nested operators in in',()=>{
  for(const source of [
    'const cond={$gt:5}; db.c.find({$or:[{a:cond},{a:10}]})',
    'db.c.find({$or:[{a:cfg.cond},{a:10}]})',
    'db.c.find({$or:[{a:makeCond()},{a:10}]})'
  ]) assert.equal(optimize(source).text,source);
  assert.ok(optimize('db.c.find({$or:[{a:ObjectId("000000000000000000000001")},{a:ObjectId("000000000000000000000002")}]})').applied.some(f=>f.code==='or-to-in'));
});

test('regression O4: bare-input unknown identity is independent of placeholder spelling',()=>{
  const explicit=optimize('db.collection.find({tenantId:1})',{apply:false});
  assert.equal(explicit.targets[0].collection,'collection');
  assert.equal(explicit.indexes[0].collection,'collection');
  for(const source of ['{tenantId:1}','[{$match:{tenantId:1}}]']){
    const report=optimize(source,{apply:false});
    assert.equal(report.targets[0].collection,null);
    assert.equal(report.indexes.length,0);
  }
  const foreign=optimize('[{$lookup:{from:"users",localField:"a",foreignField:"uid",as:"u"}}]',{apply:false});
  assert.ok(foreign.indexes.some(r=>r.collection==='users'));
});

test('regression O5: generated change stream envelope does not receive ordinary collection indexes',()=>{
  const report=optimize('db.events.watch([{$match:{operationType:"insert"}}])',{apply:false});
  assert.equal(report.targets[0].kind,'watch');
  assert.deepEqual(report.indexes,[]);
});

test('regression O6: parser failures disclose incomplete analysis to public callers',()=>{
  const source='db.c.find({a:})';
  assert.ok(parse(source)[1].length);
  const report=optimize(source);
  assert.equal(report.applied.length,0);
  assert.match(formatReport(report),/parse|incomplete/i);
  assert.ok(toDict(report).findings.length);
});

test('regression O7: wide-filter accumulation and identity membership have linear work',()=>{
  const n=1024;
  const keys=Array.from({length:n},(_,i)=>'k'+String(i).padStart(5,'0'));
  const source='db.c.find({'+keys.map(k=>k+':0').join(',')+',tail:{$ne:1}})';
  const full='db.c.find({'+Array.from({length:16384},(_,i)=>'k'+String(i).padStart(5,'0')+':0').join(',')+'})';
  assert.ok(full.length<200000);
  const wide=optimize(full,{apply:false});
  assert.equal(wide.targets.length,1);
  assert.ok(wide.findings.some(f=>f.code==='index-too-wide'));
  assert.deepEqual(wide.indexes,[]);
  const concat=Array.prototype.concat,includes=Array.prototype.includes;
  let copied=0,visited=0;
  Array.prototype.concat=function(...args){
    for(const values of [this,...args]) if(Array.isArray(values) && values.length && values[0] && typeof values[0]==='object' && Object.hasOwn(values[0],'field') && Object.hasOwn(values[0],'kind')) copied+=values.length;
    return Reflect.apply(concat,this,args);
  };
  Array.prototype.includes=function(value,...args){
    if(typeof value==='string' && /^k[0-9]+$/.test(value)) visited+=this.length;
    return Reflect.apply(includes,this,[value,...args]);
  };
  let report;
  try{report=optimize(source,{apply:false});}
  finally{Array.prototype.concat=concat;Array.prototype.includes=includes;}
  assert.ok(report.findings.some(f=>f.code==='negation'));
  assert.ok(report.findings.some(f=>f.code==='index-too-wide'));
  assert.equal(report.indexes.length,0);
  assert.ok(copied+visited<=16*n,`copied ${copied}, membership visits ${visited}, linear budget ${16*n}`);
});

test('regression O8: visible finding count agrees across report and serialization',()=>{
  const report=optimize('db.c.aggregate([{$set:{a:1}},{$match:{b:1}}])',{apply:false});
  const visible=toDict(report).findings;
  assert.equal(visible.length,1);
  assert.match(formatReport(report).split('\n')[0],/1 medium/);
});

test('regression O9: large or rewrites do not promise unconditional sort compatibility',()=>{
  const branches=Array.from({length:201},(_,i)=>'{a:'+i+'}').join(',');
  const report=optimize('db.c.find({$or:['+branches+']}).sort({b:1})');
  assert.ok(report.findings.some(f=>f.code==='in-blocks-sort'));
  const applied=report.applied.find(f=>f.code==='or-to-in');
  assert.ok(applied);
  assert.doesNotMatch(applied.message,/and sort-compatible\.$/);
});

test('paired independent contract: concrete foreign lookup index survives unknown local collection',()=>{
  const report=optimize('[{$lookup:{from:"stores",localField:"storeId",foreignField:"storeId",as:"store"}}]',{apply:false});
  assert.equal(report.targets[0].collection,null);
  assert.equal(report.indexes.length,1);
  assert.equal(report.indexes[0].collection,'stores');
  assert.deepEqual(report.indexes[0].keys,[['storeId',1]]);
  assert.equal(report.indexes[0].rationale,'$lookup from an unspecified collection probes stores.storeId once per input document; without this index each probe is a collection scan.');
});


test('paired independent contract: leading pipeline OR keeps branches separate for index advice',()=>{
  const source='db.c.aggregate([{$match:{tenant:1,$or:[{a:1},{b:2}]}},{$sort:{createdAt:-1}}])';
  for(const apply of [true,false]){
    const report=optimize(source,{apply});
    assert.equal(report.text,source);
    assert.equal(report.indexes.length,2);
    assert.deepEqual(report.indexes.map(r=>r.collection),['c','c']);
    assert.deepEqual(report.indexes.map(r=>r.keys),[
      [['tenant',1],['a',1],['createdAt',-1]],
      [['tenant',1],['b',1],['createdAt',-1]]
    ]);
  }
});

test('independent primary contract: explicit null and array blockers suppress coverage advice',()=>{
  for(const source of [
    'db.c.find({a:null},{a:1,_id:0})',
    'db.c.find({a:[1,2]},{a:1,_id:0})',
    'db.c.find({a:{$eq:null}},{a:1,_id:0})',
    'db.c.find({a:{$eq:[1,2]}},{a:1,_id:0})',
    'db.c.find({tenant:1,a:{$elemMatch:{$gt:1}}},{tenant:1,_id:0})',
    'db.c.find({$and:[{a:null}]},{a:1,_id:0})'
  ]){
    const report=optimize(source,{apply:false});
    assert.ok(report.indexes.length);
    for(const rec of report.indexes) assert.doesNotMatch(rec.rationale,/May cover|PROJECTION_COVERED|0 documents examined/);
  }
});

test('independent primary contract: unknown schema leaves projection coverage conditional',()=>{
  const report=optimize('db.c.find({a:1},{a:1,_id:0})',{apply:false});
  assert.match(report.indexes[0].rationale,/May cover the projection; null equality, multikey values and schema details can require document reads\. Confirm coverage with explain\(\)\./);
  assert.doesNotMatch(report.indexes[0].rationale,/PROJECTION_COVERED|0 documents examined/);
});
