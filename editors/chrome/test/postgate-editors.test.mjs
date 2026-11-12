// Focused regressions for corroborated gate2 editor findings. Synthetic DOM and local files only.
import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { pageFixture, sessionStore, flush } from "./dom-fixture.mjs";
import { grabSelection, pickSelection, consumeHandoff, HANDOFF_PREFIX } from "../lib/capture.js";
import { snippet, dedupe, SearchIndex } from "../lib/textsearch.js";
import { loadIndex } from "../lib/store.js";
import { startAutoUpdate, buildId } from "../lib/autoupdate.js";
import { appComplete } from "./app-completion.mjs";
import { loadCapture, hasPackagedData } from "./extension-under-test.mjs";
import { optimize } from "../lib/optimize.js";

const plain = parts => parts.map(p => p.text).join("");
function files(extra = {}) { return { 'meta.json':{total_tokens:1,...extra},
 'chunks.json':{paths:['synthetic.md'],sources:['test'],kinds:['doc'],rows:[[0,0,0,1,'synthetic','synthetic',-1]]},
 'terms.json':{synthet:[1,0]},'postings.bin':Uint8Array.of(0,0,0,0),'weights.bin':Uint8Array.of(1,0),'doclen.bin':Uint8Array.of(1,0,0,0) }; }
function updater(builds) {
 let at=0;const values={};const api={runtime:{getURL:x=>x,reloads:0,reload(){this.reloads++;}},
 alarms:{get:async()=>({}),create:async()=>{},onAlarm:{addListener(){}}},
 storage:{session:{get:async k=>({[k]:values[k]}),set:async o=>Object.assign(values,o),remove:async k=>{delete values[k];}}}};
 const fetchImpl=async()=>{const value=builds[Math.min(at++,builds.length-1)];return {ok:Boolean(value),json:async()=>value};};
 return {api,fetchImpl};
}

test('failed settings persistence leaves semantic runtime off',async()=>{
 const p=pageFixture('app.js');p.$('ollama-host').value='http://127.0.0.1:11434';
 p.chrome.storage.local.set=async()=>{throw Error('synthetic save failure');};await p.enableOllama();
 assert.equal(p.state.settings.semantic,false);assert.equal(p.state.mode,'keyword');assert.match(p.$('ollama-status').textContent,/synthetic save failure/);
 const html=readFileSync(new URL('../app.html',import.meta.url),'utf8');assert.match(html,/<p[^>]*id="ollama-status"[^>]*role="status"[^>]*aria-atomic="true"/);
});
test('truncation warning survives unchanged reruns and tool transfer, and clears on input',async()=>{
 const p=pageFixture('app.js',{hash:'#lint?handoff=synthetic'});p.wire();
 await p.chrome.storage.session.set({[HANDOFF_PREFIX+'synthetic']:{tab:'lint',text:'db.c.find({})',truncated:true,ts:Date.now()}});
 assert.equal(await p.consumePending(),true);if(p.drainNavigation)await p.drainNavigation();
 vm.runInContext('runLint()',p.context);assert.match(p.$('lint-out').textContent,/first 200,000/);
 await p.$('lint-to-opt').emit('click');if(p.drainNavigation)await p.drainNavigation();assert.match(p.$('opt-out').textContent,/first 200,000/);
 vm.runInContext('runOptimize()',p.context);assert.match(p.$('opt-out').textContent,/first 200,000/);
 p.$('opt-input').value='db.c.find({x:1})';await p.$('opt-input').emit('input');vm.runInContext('runOptimize()',p.context);
 assert.doesNotMatch(p.$('opt-out').textContent,/first 200,000/);
});
test('selecting a late passage only allocates the displayed DOM and retains fence context',async()=>{
 const hit={id:501,path:'synthetic.md',line:502,heading:'synthetic',source:'test',kind:'doc',score:1,via:'keyword',text:'inside\n```'};
 const chunks=[...Array.from({length:500},(_,i)=>({id:i,line:i+1,text:'synthetic paragraph'})),{id:500,line:501,text:'```js'},hit];
 const idx={vectors:false,meta:{},keyword:()=>[hit],document:()=>({chunks})};
 const p=pageFixture('app.js',{deps:{getIndex:async()=>idx}});let nodes=0;const create=p.document.createElement;
 p.document.createElement=tag=>{nodes++;return create(tag);};await p.runSearch('synthetic');
 assert.ok(nodes<100,`created ${nodes} nodes`);assert.equal(p.$('detail').querySelector('pre').textContent,'inside');
});
test('Linux help copy payloads have one destination each',async()=>{
 const copied=[];const p=pageFixture('app.js',{globals:{setTimeout:()=>0}});p.context.navigator.clipboard.writeText=async x=>copied.push(x);
 vm.runInContext('showOllamaHelp(true)',p.context);for(const button of p.$('ollama-help').querySelectorAll('button'))await button.emit('click');
 assert.ok(copied.includes('sudo systemctl edit ollama'));assert.ok(copied.includes('sudo systemctl restart ollama'));
 const override=copied.find(x=>x.startsWith('[Service]'));assert.ok(override);assert.doesNotMatch(override,/sudo|systemctl/);
});
test('focused leaf frame beats a longer stale selection',()=>{
 const capture=(focused,tag='TEXTAREA')=>vm.runInNewContext(`(${grabSelection.toString()})()`,{document:{activeElement:{tagName:tag,value:'synthetic',selectionStart:0,selectionEnd:9},hasFocus:()=>focused},window:{getSelection:()=>''}});
 const current=capture(true);assert.equal(current.text,'synthetic');assert.equal(current.focused,true);assert.equal(capture(false).focused,false);assert.equal(capture(true,'IFRAME').focused,false);
 assert.equal(pickSelection([{result:{text:'very long stale selection',focused:false}},{result:{text:'current',focused:true}}]),'current');
 const top={document:{activeElement:null}};top.top=top;top.parent=top;const currentElement={};top.document.activeElement=currentElement;
 const child={top,parent:top,frameElement:currentElement,getSelection:()=>''};
 const result=vm.runInNewContext(`(${grabSelection.toString()})()`,{document:{activeElement:{tagName:'TEXTAREA',value:'active',selectionStart:0,selectionEnd:6},hasFocus:()=>false},window:child});
 assert.equal(result.focused,true,'same-origin focus chain survives popup focus');
 assert.equal(pickSelection([{result:{text:'stale',focused:false}},{result:{text:'',focused:true}}]),'');
});
test('origin lock makes overlapping separate-context handoff consumption one-time',async()=>{
 const original=sessionStore({[HANDOFF_PREFIX+'shared']:{text:'synthetic',ts:1}});
 const session={...original,get:async k=>{const value=await original.get(k);await Promise.resolve();return value;}};
 let queue=Promise.resolve();const locks={request(_key,work){const result=queue.then(work);queue=result.catch(()=>{});return result;}};
 const results=await Promise.all([consumeHandoff(session,'shared',1,locks),consumeHandoff(session,'shared',1,locks)]);
 assert.equal(results.filter(Boolean).length,1);assert.equal(results.find(Boolean).text,'synthetic');
});
test('failed startup identity reloads once when readable metadata returns',async()=>{
 const f=updater([null,{commit:'B'}]);const h=startAutoUpdate(f.api,f.fetchImpl);await h.ready;assert.equal(await h.check(),true);assert.equal(await h.check(),false);assert.equal(f.api.runtime.reloads,1);
});
test('same-commit rebuilds have distinct package identities and reload',async()=>{
 const a={commit:'c1',version:'1',built_at:'synthetic-a',vectors:true},b={...a,built_at:'synthetic-b',vectors:false};assert.notEqual(buildId(a),buildId(b));
 const f=updater([a,b]);const h=startAutoUpdate(f.api,f.fetchImpl);await h.ready;assert.equal(await h.check(),true);assert.equal(f.api.runtime.reloads,1);
});
test('empty exported recipes do not block searchable metadata',async()=>{
 const f=files({recipes:[{name:'empty',title:'Empty',summary:'',applies_to:[],path:null}]});const idx=await loadIndex(async k=>f[k]??null);
 assert.equal(idx.keyword('synthetic').length,1);assert.deepEqual(idx.meta.recipes,[]);
});
test('intentional no-data manifest skips absent resource fetch',async()=>{
 const previousChrome=globalThis.chrome,previousFetch=globalThis.fetch;let fetched=0;
 try{globalThis.chrome={runtime:{getManifest:()=>({mdbx_data:false}),getURL:x=>x}};globalThis.fetch=async()=>{fetched++;throw TypeError('synthetic unavailable resource');};
 const {getIndex}=await import(new URL('../lib/store.js?no-data',import.meta.url));assert.equal(await getIndex(),null);assert.equal(fetched,0);
 }finally{globalThis.chrome=previousChrome;globalThis.fetch=previousFetch;}
});
test('snippet boundaries retain operators, signs and closing punctuation',()=>{
 for(const [text,q] of [['$match','match'],['-1','1'],['value.','value']])assert.equal(plain(snippet(text,q)),text);
 assert.equal(snippet('$match','match')[0].hit,false);
});
test('dedupe uses Python split whitespace, preserving FEFF identity',()=>{
 const hit=text=>({text});assert.deepEqual(dedupe([hit('alpha beta'),hit('alpha\u0085beta'),hit('unique')],2).map(h=>h.text),['alpha beta','unique']);
 for(const space of ['\u001c','\u001d','\u001e','\u001f'])assert.equal(dedupe([hit('a b'),hit('a'+space+'b')],2).length,1);
 assert.equal(dedupe([hit('a b'),hit('a\ufeffb')],2).length,2);
});
test('source filtering matches SQLite ASCII-only LIKE folding',()=>{
 const idx=new SearchIndex({meta:{total_tokens:1},chunks:{paths:['synthetic.md'],sources:['äABC'],kinds:['doc'],rows:[[0,0,0,1,'synthetic','synthetic',-1]]},vocab:{synthet:[1,0]},ids:Uint32Array.of(0),wts:Uint16Array.of(1),doclen:Uint32Array.of(1)});
 assert.equal(idx.allowed(0,null,'Ä'),false);assert.equal(idx.allowed(0,null,'abc'),true);assert.equal(idx.allowed(0,null,'äa'),true);
});
test('ordered list context continues across adjacent chunks and resets across a real gap',()=>{
 const p=pageFixture('lib/ui.js'),context={fence:null};const first=p.renderMarkdown('1. first\n1. second',{context,line:1});const second=p.renderMarkdown('1. third\n1. fourth',{context,line:3});
 assert.equal(first.querySelector('ol').getAttribute('start'),'1');assert.equal(second.querySelector('ol').getAttribute('start'),'3');
 assert.equal(p.renderMarkdown('1. new list',{context,line:6}).querySelector('ol').getAttribute('start'),'1');
});
test('malformed links preserve literal text and valid link behavior',()=>{
 const p=pageFixture('lib/ui.js');const source='[x](https://'.repeat(4000);assert.equal(p.renderMarkdown(source).textContent,source);
 const rendered=p.renderMarkdown('before [safe](https://example.invalid/path) after');assert.equal(rendered.querySelector('a').getAttribute('href'),'https://example.invalid/path');assert.equal(rendered.textContent,'before safe after');
});
test('popup retains malformed command diagnostics and ordinary-question fallback',async()=>{
 const p=pageFixture('popup.js',{deps:{optimize,getIndex:async()=>null}});p.run('{"find":"orders","filter":{"x":}}');await flush();assert.equal(p.$('result').hidden,false);assert.match(p.$('result').textContent,/Incomplete analysis/);assert.equal(p.$('input-section').open,true);
 p.run('why is my index not used');await flush();assert.match(p.$('result').textContent,/No query found, and this build has no search data/);
});
test('DOM fixture shares anchor identity, has valid report stubs and drains navigation',async()=>{
 const p=pageFixture('app.js');assert.equal(p.$('nav-search'),p.tabs[0]);p.wire();
 p.$('opt-input').value='synthetic';assert.doesNotThrow(()=>vm.runInContext('runOptimize()',p.context));assert.match(p.$('opt-out').textContent,/No query found/);
 p.go('lint');if(p.drainNavigation)await p.drainNavigation();assert.equal(p.$('tab-lint').hidden,false);assert.equal(p.$('tab-search').hidden,true);assert.equal(p.$('nav-search').getAttribute('aria-selected'),'false');
});
test('debug completion waits for app readiness before empty search',async()=>{
 const p=pageFixture('app.js',{hash:'#search'});const complete=()=>vm.runInContext(`(${appComplete.toString()})()`,p.context);
 assert.equal(complete(),false);await vm.runInContext('main()',p.context);assert.equal(complete(),true);
});
test('debug completion accepts unknown route fallback',async()=>{
 const p=pageFixture('app.js',{hash:'#unknown'});await vm.runInContext('main()',p.context);
 const lookup=p.document.getElementById;p.document.getElementById=id=>id==='tab-unknown'?null:lookup(id);
 assert.equal(vm.runInContext(`(${appComplete.toString()})()`,p.context),true);
});
test('debug completion accepts an empty rendered recipe list',async()=>{
 const p=pageFixture('app.js',{hash:'#recipes',deps:{getIndex:async()=>({meta:{recipes:[]}})}});await vm.runInContext('main()',p.context);
 assert.equal(p.$('recipes').textContent,'');assert.equal(vm.runInContext(`(${appComplete.toString()})()`,p.context),true);
});
test('e2e helpers use selected build capture and skip data only for an absent file',async()=>{
 const root=mkdtempSync(join(tmpdir(),'synthetic-extension-#-'));try{mkdirSync(join(root,'lib'));writeFileSync(join(root,'package.json'),'{"type":"module"}');writeFileSync(join(root,'lib/capture.js'),'export function grabSelection(){return "selected-build";}');assert.equal((await loadCapture(root)).grabSelection(),'selected-build');
 let checks=0;assert.equal(await hasPackagedData(root,async()=>{checks++;return true;}),false);assert.equal(checks,0);
 mkdirSync(join(root,'data'));writeFileSync(join(root,'data/meta.json'),'{}');await assert.rejects(hasPackagedData(root,async()=>{throw Error('synthetic fetch');}),/synthetic fetch/);await assert.rejects(hasPackagedData(root,async()=>false),/could not be loaded/);assert.equal(await hasPackagedData(root,async()=>true),true);
 }finally{rmSync(root,{recursive:true,force:true});}
});

test('search batch rejects nonfinite scores instead of serializing null',()=>{
 const root=mkdtempSync(join(tmpdir(),'synthetic-search-batch-'));try{
 const data=files({vectors:{dim:1,count:1}});data['chunks.json'].rows[0][6]=0;data['vectors.bin']=Uint8Array.of(127);
 for(const [name,value] of Object.entries(data))writeFileSync(join(root,name),value instanceof Uint8Array?value:JSON.stringify(value));
 const result=spawnSync(process.execPath,[fileURLToPath(new URL('./search-batch.mjs',import.meta.url)),root],{input:JSON.stringify([{q:'synthetic',qvec:[1e308]}]),encoding:'utf8',timeout:3000});
 assert.equal(result.error,undefined);assert.notEqual(result.status,0);assert.match(result.stderr,/batch position 0: nonfinite search score/);assert.doesNotMatch(result.stdout,/null/);
 }finally{rmSync(root,{recursive:true,force:true});}
});

test('finding code guard includes object-form findings',()=>{
 const source=readFileSync(new URL('./ui.test.mjs',import.meta.url),'utf8');const start=source.indexOf('function findingCodes('),end=source.indexOf('\ntest(',start);
 const extract=vm.runInNewContext(`(${source.slice(start,end)})`);assert.equal(extract('items.push({severity:HIGH,code:"synthetic-object"})').has('synthetic-object'),true);
});
test('HTML sink guard handles comments and string escapes in constant property names',()=>{
 const source=readFileSync(new URL('./ui.test.mjs',import.meta.url),'utf8');const start=source.indexOf('function hasUnsafeSink('),end=source.indexOf('\ntest(',start);
 const guard=vm.runInNewContext(`(${source.slice(start,end)})`);
 for(const example of ['el["in" + /* synthetic */ "nerHTML"] = value','el["in" + // synthetic\n "nerHTML"] = value','el["in" + "ner\\x48TML"] = value'])assert.equal(guard(example),true);
 assert.equal(guard('el.textContent = value'),false);
});
