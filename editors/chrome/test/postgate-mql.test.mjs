import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parse} from '../lib/parser.js';
import {analyze} from '../lib/analyze.js';
import {normalize} from '../lib/normalize.js';
import {optimize} from '../lib/optimize.js';

test('paired analyzer binding and nested-call traversal',()=>{
 assert.deepEqual(analyze('var spec={a:1};db.c.find(spec);var spec=[{$limit:1}];db.c.aggregate(spec)').diagnostics,[]);
 assert.ok(analyze('db.c.findOne(db.filters.findOne({n:{$in:1}}))').diagnostics.some(d=>d.code==='bad-argument'));
});
test('paired scalar projection and contextual contract validation',()=>{
 assert.deepEqual(analyze('db.c.find({}, {scores:{$elemMatch:{$gte:80}}})').diagnostics,[]);
 for(const source of ['db.c.aggregate([{$group:{_id:null,m:{$median:42}}}])','db.c.aggregate([{$documents:42}])','db.c.updateOne({},{$pull:{items:{score:{$in:1}}}})','db.c.find({$text:{$search:7}})']) assert.ok(analyze(source).diagnostics.some(d=>d.code==='bad-argument'));
 assert.deepEqual(analyze('db.c.aggregate([{$project:{a:{$and:[]},b:{$or:[]}}}])').diagnostics,[]);
});
test('paired unknown-key controls are visible and UTF8 safe',()=>{
 const key='$'+String.fromCodePoint(0x202e)+'unknown';
 const messages=analyze('db.c.find({'+JSON.stringify(key)+':1})').diagnostics.map(d=>d.message);
 assert.ok(messages.length);assert.ok(messages.every(m=>!m.includes(String.fromCodePoint(0x202e))));
});
test('declarations retain source and role-sensitive rewrites',()=>{
 const declaration='const f={a:1};\n{find:"c",filter:f}';assert.equal(normalize(declaration).text,declaration);
 for(const source of ['const f={$or:[{a:1},{a:2}]};db.c.find(f);db.c.replaceOne({_id:1},f)','const q={$or:[{a:1},{a:2}]};db.c.find(q);lookup[q.$or];','var p=[{$sort:{x:1}},{$match:{y:1}}];capture(p);db.c.aggregate(p);var p=[];']) assert.equal(optimize(source).text,source);
 assert.ok(optimize('const f={$or:[{a:1},{a:2}]};db.c.find(f)').applied.some(f=>f.code==='or-to-in'));
});
test('computed keys, templates, numeric property keys and empty brackets',()=>{
 const text='lookup[`left\nright`]';assert.ok(parse(text)[0][0].node.walk().some(n=>n.kind==='string'&&n.value==='left\nright'));
 assert.ok(normalize('{find:"c",filter:{a:'+text+'}}').text.includes('`left\nright`'));
 for(const source of ['db[].find({a:1})','db[/*empty*/].find({a:1})'])assert.ok(parse(source)[1].length);
 for(const sep of ['\r','\r\n'])assert.equal(normalize('{find:`c'+sep+'x`,filter:{}}').queries[0].collection,'c\nx');
 assert.deepEqual(parse('{1.0:1,1:2}')[0][0].node.props.map(p=>p.key),['1','1']);
});
test('declaration analysis visits each tree a bounded number of times',()=>{
 const Node=parse('{}')[0][0].node.constructor,original=Node.prototype.walk;
 const counts=[];
 for(const n of [200,400]){
  let visits=0;Node.prototype.walk=function(...args){const out=Reflect.apply(original,this,args);visits+=out.length;return out;};
  try{optimize(Array.from({length:n},(_,i)=>'const v'+i+'=0;').join('')+'db.c.find({a:1})',{apply:false});}finally{Node.prototype.walk=original;}
  counts.push(visits);
 }
 assert.ok(counts[0]>0&&counts[1]<=3*counts[0]+100,JSON.stringify(counts));
});
