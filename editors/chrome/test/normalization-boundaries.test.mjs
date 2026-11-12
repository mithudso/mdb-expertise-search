import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalize} from '../lib/normalize.js';
import {parse} from '../lib/parser.js';
import {optimize} from '../lib/optimize.js';

test('regression N1: regex quote does not alter template literal value',()=>{
  const source='{find:"c",filter:{r:/`/,s:`left\nright`}}';
  const [original,errors]=parse(source);
  assert.deepEqual(errors,[]);
  const filter=original[0].node.props.find(p=>p.key==='filter').value;
  const expected=filter.props.find(p=>p.key==='s').value.value;
  const normalized=normalize(source);
  const [statements,normalizedErrors]=parse(normalized.text);
  assert.deepEqual(normalizedErrors,[]);
  const actual=statements[0].node.items[0].props.find(p=>p.key==='s').value.value;
  assert.equal(actual,expected);
});

test('regression N2: raw unsafe integer evidence remains an exact decimal string',()=>{
  const source='{attr:{command:{find:"c",filter:{}},docsExamined:9007199254740993,nreturned:1}}';
  const result=normalize(source);
  assert.equal(result.queries[0].evidence.docsExamined,'9007199254740993');
  assert.ok(!optimize(source).findings.some(f=>f.code==='log-scan-ratio'));
});

test('regression N3: valid large batch is not converted into function arguments',()=>{
  const n=200000;
  const source=JSON.stringify({delete:'c',deletes:Array.from({length:n},()=>({q:{},limit:1}))});
  const result=normalize(source);
  assert.equal(result.queries.length,n);
});

test('regression N4: nonoverlapping header errors are visited linearly',()=>{
  const counts=[];
  for(const n of [150,300]) {
    const source='@\n{attr:{command:{find:"c",filter:{}}}}\n'.repeat(n);
    const push=Array.prototype.push;let visits=0;
    Array.prototype.push=function(...values){
      values=values.map(value=>value && typeof value==='object' && Object.hasOwn(value,'message') && Object.hasOwn(value,'start') && Object.hasOwn(value,'end') ? new Proxy(value,{get(target,key,receiver){if(key==='start'||key==='end')visits++;return Reflect.get(target,key,receiver);}}):value);
      return Reflect.apply(push,this,values);
    };
    let result;try{result=normalize(source);}finally{Array.prototype.push=push;}
    assert.equal(result.queries.length,n);counts.push(visits);
  }
  assert.ok(counts[0]>0 && counts[1]<=3*counts[0]+100,JSON.stringify(counts));
});

test('regression N2a: unsafe raw integer measurements do not enter P9 arithmetic',()=>{
  const source='{attr:{command:{find:"c",filter:{}},docsExamined:9007199254740993,nreturned:1}}';
  assert.ok(!optimize(source).findings.some(f=>f.code==='log-scan-ratio'));
});

test('regression N3a: 100000 operation control batch is retained',()=>{
  const n=100000;
  const source=JSON.stringify({delete:'c',deletes:Array.from({length:n},()=>({q:{},limit:1}))});
  assert.equal(normalize(source).queries.length,n);
});


test('paired normalization: legacy newline spacing remains outside protected literals',()=>{
  const source='{find:"c",filter:{\n  a:1,\n  b:2\n}}';
  assert.equal(normalize(source).text,'db.getCollection("c").find({a:1, b:2 })\n');
  const literal='{find:"c",filter:{r:/"/,s:`a"b\nc`}}';
  const [statements,errors]=parse(normalize(literal).text);
  assert.deepEqual(errors,[]);
  const filter=statements[0].node.items[0];
  assert.equal(filter.props.find(prop=>prop.key==='s').value.value,'a"b\nc');
});
