import { fileURLToPath } from "node:url";
// Regressions use synthetic data and the maintained runtime modules.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
const root = fileURLToPath(new URL("../../../", import.meta.url));
const { pageFixture, backgroundFixture, sessionStore, deferred, flush } = await import(new URL('./dom-fixture.mjs', import.meta.url));
const { saveHandoff, consumeHandoff, MAX_INPUT } = await import(new URL('../lib/capture.js', import.meta.url));
const { toMarkdown } = await import(new URL('../lib/report.js', import.meta.url));
const { loadIndex } = await import(new URL('../lib/store.js', import.meta.url));
const { startAutoUpdate, SESSION_KEY, ALARM } = await import(new URL('../lib/autoupdate.js', import.meta.url));
const read = name => readFileSync(root + '/editors/chrome/' + name, 'utf8');
function files(meta = {total_tokens: 1}) { return { 'meta.json': meta,
 'chunks.json': {paths:['synthetic.md'],sources:['test'],kinds:['doc'],rows:[[0,0,0,1,'heading','synthetic',-1]]},
 'terms.json':{synthetic:[1,0]}, 'postings.bin':new Uint8Array(4),'weights.bin':Uint8Array.of(1,0),'doclen.bin':Uint8Array.of(1,0,0,0) }; }
function index() { return { vectors:false,dim:0,n:1, facets:()=>[],keyword:()=>[],meta:{ chunks:1,files:1,sources:[],by_kind:{},terms:1,postings:1,vectors:null,recipes:[],built_at:'synthetic',mdbx_version:'test' } }; }
function scheduler(builds, failWrite=false, failLookup=false) {
 let at=0, writes=0, lookups=0;const values={},listeners=[],created=[];
 const api={alarms:{get:async()=>{if(failLookup&&++lookups===1)throw Error('synthetic lookup');return null;}, create:async(name,opts)=>created.push([name,opts]),onAlarm:{addListener:fn=>listeners.push(fn)}},
 runtime:{getURL:x=>x,reloaded:0,reload(){this.reloaded++;}},storage:{session:{get:async key=>({[key]:values[key]}),set:async obj=>{if(failWrite&&++writes===1)throw Error('synthetic write');Object.assign(values,obj);},remove:async key=>{delete values[key];}}}};
 const fetchImpl=async()=>({ok:true,json:async()=>({commit:builds[Math.min(at++,builds.length-1)]})});
 return {api,fetchImpl,values,listeners,created};
}
test('capture truncation metadata survives the handoff',async()=>{ const s=sessionStore();const id=await saveHandoff(s,{text:'x'.repeat(MAX_INPUT+1)});assert.equal((await consumeHandoff(s,id)).truncated,true); });
test('background creation failure is contained and removes only its handoff',async()=>{const b=backgroundFixture();const preserved={'selectionHandoff:other':{text:'preserved',ts:Date.now()},last:'preserved last'};await b.session.set(preserved);let attempted=0;b.chrome.tabs.create=async()=>{attempted++;throw Error('synthetic launch failure');};await assert.doesNotReject(b.handlers.click({menuItemId:'mql-lint-selection',selectionText:'synthetic'}));assert.equal(attempted,1);assert.deepEqual(b.session.values,preserved);});
test('report prose preserves named character references literally',()=>{ const rep={inputQueries:1,inputKind:'mongosh',interpreted:null,text:'',indexes:[],evidence:[],applied:[],findings:[{code:'unknown',severity:'medium',pass:'P1',message:'pattern /Tom &amp; Jerry/'}]}; assert.ok(toMarkdown(rep).includes("Tom " + String.fromCharCode(92) + "&amp; Jerry")); });
test('known startup identity survives failed session persistence',async()=>{const f=scheduler(['c1','c2','c2'],true);const h=startAutoUpdate(f.api,f.fetchImpl);await h.ready;await h.check();assert.equal(f.api.runtime.reloaded,1);});
test('failed alarm initialization automatically retries scheduling',{timeout:2000},async()=>{const f=scheduler(['c1'],false,true);const pending=[];const h=startAutoUpdate(f.api,f.fetchImpl,{schedule:fn=>pending.push(fn)});await h.ready;const created=deferred();f.api.alarms.create=async(...args)=>{f.created.push(args);created.resolve();};for(const retry of pending)retry();await created.promise;assert.equal(f.created.length,1);});
for(const meta of [false,0,'']) test('invalid falsy metadata rejects: '+JSON.stringify(meta),async()=>{const f=files(meta);await assert.rejects(loadIndex(async name=>f[name]??null));});
for(const field of ['sources','recipes'])test('UI-incompatible metadata rejects '+field,async()=>{const f=files({total_tokens:1,[field]:{}});await assert.rejects(loadIndex(async name=>f[name]??null),/Invalid or inconsistent packaged meta.json/);});
test('JSON parser diagnostics never expose content',async()=>{let error;try {await loadIndex(async()=>JSON.parse('SYNTH_CANARY!'));}catch(e){error=e;}assert.ok(error);assert.doesNotMatch(String(error),/SYNTH_CANARY/);});
test('blank optimizer submission clears previous report',()=>{const p=pageFixture('app.js');p.$('opt-out').textContent='previous report';p.$('opt-input').value='  ';vm.runInContext('runOptimize()',p.context);assert.equal(p.$('opt-out').textContent,'');});
test('mode selection is represented by navigation URL',async()=>{const p=pageFixture('app.js',{hash:'#search?q=synthetic&mode=keyword',deps:{getIndex:async()=>index()}});p.wire();p.$('q').value='synthetic';p.$('mode').value='hybrid';await p.$('mode').emit('change');await flush();assert.equal(new URLSearchParams(p.location.hash.split('?')[1]).get('mode'),'hybrid');});
test('Enter on copy button preserves search route',async()=>{const p=pageFixture('app.js');p.wire();p.state.hits=[{path:'synthetic.md',line:1}];p.state.selected=0;const button=p.document.createElement('button');button.focus();await p.document.emit('keydown',{key:'Enter'});assert.equal(p.location.hash,'#search');});
test('lint rendering handles a wide diagnostic list without stale output',()=>{const d={line:0,column:0,severity:'warning',code:'synthetic',message:'synthetic'};const p=pageFixture('app.js',{deps:{diagnosticsToDicts:()=>Array(150000).fill(d)}});p.$('lint-input').value='synthetic';p.$('lint-out').textContent='previous report';let diagnostics=0;const h=p.context.h;p.context.h=(tag,attrs,...children)=>{if(attrs?.class==='diag sev-warning')diagnostics++;return h(tag,attrs,...children);};assert.doesNotThrow(()=>vm.runInContext('runLint()',p.context));assert.equal(diagnostics,150000);assert.doesNotMatch(p.$('lint-out').textContent,/previous report/);assert.match(p.$('lint-out').textContent,/150000 warning/);});
test('delayed About statistics preserve host edits',async()=>{const loading=deferred();const p=pageFixture('app.js',{deps:{getIndex:()=>loading.promise}});const work=vm.runInContext('renderAbout()',p.context);p.$('ollama-host').value='http://localhost:11435';loading.resolve(index());await work;assert.equal(p.$('ollama-host').value,'http://localhost:11435');});
test('Linux origin recovery includes the required Service section',()=>{const p=pageFixture('app.js');vm.runInContext('showOllamaHelp(true)',p.context);assert.ok(p.$("ollama-help").textContent.includes("[Service]"));});
test('recipe grid can shrink below its nominal 280px track',()=>{assert.ok(read('app.css').includes('minmax(min(100%, 280px), 1fr)'));});
test('shortcut documentation states search-input Enter submits',()=>{assert.match(read('app.html'),/Enter<\/kbd>[^<]*(?:submits|search box|input)/);});
