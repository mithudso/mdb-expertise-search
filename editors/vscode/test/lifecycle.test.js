"use strict";
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const Module=require('node:module');
const {spawnTransport,stopTransport,settleStartup}=require('../server-process');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

class Child extends EventEmitter {
 constructor(pid){super();this.pid=pid;this.signals=[];this.stdin=new EventEmitter();this.stdout=new EventEmitter();this.stderr=new EventEmitter();this.closed=false;}
 close(){if(this.closed)return;this.closed=true;this.emit('close',0,null);}
 kill(signal){this.signals.push(signal);this.close();return true;}
}
function harness(modes){
 const children=[],clients=[],live=new Set();let restart,errors=0,attempt=0;
 const fakeSpawn=(command,args,options)=>{assert.equal(command,'mql-lsp');assert.deepEqual(args,['--stdio']);assert.equal(options.stdio,'pipe');const child=new Child(100+children.length);children.push(child);queueMicrotask(()=>{if(modes[children.length-1]==='spawn-error'){child.pid=undefined;child.emit('error',Error('synthetic spawn failure'));child.close();}else child.emit('spawn');});return child;};
 class Client {
  constructor(_id,_name,factory,options){this.factory=typeof factory==='function'?factory:async()=>spawnTransport(factory.command,factory.args,undefined,fakeSpawn).ready;this.options=options;this.state='Initial';this.cleaned=0;clients.push(this);}
  isRunning(){return this.state==='Running';}
  createDefaultErrorHandler(){return{error:()=>({action:1}),closed:()=>({action:2})};}
  start(){
   if(this.state==='Starting')return this.starting;
   if(this.disposed)return Promise.reject(Error('disposed client cannot restart'));
   this.state='Starting';const mode=modes[attempt++]||'running';this.features=true;
   this.starting=(async()=>{const child=await this.factory();this.child=child;
    await new Promise((resolve,reject)=>{
     child.once('close',()=>{this.handleConnectionClosed();reject(Error('synthetic connection closed'));});
     this.release=()=>{if(!child.closed){this.state='Running';assert.equal(live.size,0,'single running client');live.add(this);resolve();}};
     if(mode!=='pending')this.release();
    });
   })().catch(error=>{this.state='StartFailed';throw error;});
   return this.starting;
  }
  async handleConnectionClosed(){const result=this.state==='Stopping'||this.disposed?{action:1}:await (this.options.errorHandler||this.createDefaultErrorHandler()).closed();live.delete(this);if(this.features){this.cleaned++;this.features=false;}
   if(result.action===2){this.state='Initial';this.start().catch(()=>{});}else this.state=this.state==='Starting'?'StartFailed':'Stopped';
  }
  async dispose(){
   // Faithful v9 precondition: dispose itself cannot cancel Starting or StartFailed.
   if(this.state==='Starting'||this.state==='StartFailed')throw Error("Client is not running and can't be stopped. It's current state is: "+this.state);
   this.disposed=true;if(this.state==='Running'){this.state='Stopping';live.delete(this);this.child.close();this.state='Stopped';}
  }
 }
 const vscode={workspace:{getConfiguration:()=>({get:()=>undefined}),workspaceFolders:[]},commands:{registerCommand:(_name,fn)=>{restart=fn;return{dispose(){}};}},window:{showErrorMessage:()=>{errors++;}}};
 const filename=require.resolve('../extension'),original=Module._load;
 Module._load=function(name,...args){
  if(name==='vscode')return vscode;
  if(name==='vscode-languageclient/node')return{LanguageClient:Client,CloseAction:{DoNotRestart:1,Restart:2},TransportKind:{stdio:0}};
  if(name==='./server-process')return{spawnTransport:(command,args,cwd)=>spawnTransport(command,args,cwd,fakeSpawn),stopTransport,settleStartup};
  return original.call(this,name,...args);
 };
 delete require.cache[filename];const extension=require(filename);
 return{extension,children,clients,live,get restart(){return restart;},get errors(){return errors;},restore(){for(const c of clients)c.disposed=true;for(const child of children)child.close();Module._load=original;delete require.cache[filename];}};
}

test('restart cancels a pending transport, settles startup and cleans before replacement',{timeout:2000},async()=>{
 const h=harness(['pending','running']);try{const activation=h.extension.activate({subscriptions:[]});activation.catch(()=>{});await tick();assert.equal(h.children.length,1);const old=h.clients[0];const recovery=h.restart();recovery.catch(()=>{});await tick();assert.deepEqual(h.children[0].signals,['SIGTERM'],'pending recovery interrupts the transport');await recovery;await activation;
 assert.deepEqual(h.children[0].signals,['SIGTERM']);assert.equal(old.disposed,true);assert.ok(old.cleaned>=1);assert.equal(h.live.size,1);assert.equal(h.children.length,2);old.release();await tick();assert.equal(h.live.size,1);await h.extension.deactivate();assert.equal(h.live.size,0);
 }finally{h.restore();}
});
test('deactivate cancels pending initialization without creating a replacement',{timeout:2000},async()=>{
 const h=harness(['pending']);try{const activation=h.extension.activate({subscriptions:[]});activation.catch(()=>{});await tick();const stopping=h.extension.deactivate();stopping.catch(()=>{});await tick();assert.deepEqual(h.children[0].signals,['SIGTERM'],'deactivation interrupts the transport');await stopping;await activation;assert.deepEqual(h.children[0].signals,['SIGTERM']);assert.equal(h.clients[0].disposed,true);assert.equal(h.children.length,1);assert.equal(h.live.size,0);assert.equal(h.errors,0);}finally{h.restore();}
});
test('failed spawn retires StartFailed resources and reports the startup failure',{timeout:2000},async()=>{
 const h=harness(['spawn-error']);try{await h.extension.activate({subscriptions:[]});assert.equal(h.errors,1);assert.equal(h.clients[0].disposed,true);assert.ok(h.clients[0].cleaned>=1);assert.equal(h.live.size,0);await h.extension.deactivate();}finally{h.restore();}
});
test('automatic restart keeps ownership and pending automatic start can be cancelled',{timeout:2000},async()=>{
 const h=harness(['running','pending']);try{await h.extension.activate({subscriptions:[]});const first=h.children[0];first.close();await tick();assert.equal(h.clients.length,1);assert.equal(h.children.length,2);assert.equal(h.clients[0].state,'Starting');await h.extension.deactivate();assert.deepEqual(h.children[1].signals,['SIGTERM']);assert.equal(h.clients[0].disposed,true);assert.equal(h.children.length,2);assert.equal(h.live.size,0);}finally{h.restore();}
});
test('transport cancellation escalates only its owned child and awaits close',async()=>{
 const child=new Child(999);child.kill=function(signal){this.signals.push(signal);if(signal==='SIGKILL')this.close();return true;};
 const transport=spawnTransport('synthetic',[],undefined,()=>child);child.emit('spawn');await transport.ready;
 const timers=new Map();let key=0;const work=stopTransport(transport,{schedule:(fn,delay)=>{timers.set(++key,{fn,delay});return key;},cancel:id=>timers.delete(id)});
 assert.deepEqual(child.signals,['SIGTERM']);const escalation=[...timers.values()].find(t=>t.delay===500);escalation.fn();await work;assert.deepEqual(child.signals,['SIGTERM','SIGKILL']);assert.equal(timers.size,0);
});
test('unclosed owned transport rejects cleanup and preserves the handle',async()=>{
 const child=new Child(999);child.kill=function(signal){this.signals.push(signal);return true;};const transport=spawnTransport('synthetic',[],undefined,()=>child);child.emit('spawn');await transport.ready;
 const timers=new Map();let key=0;const work=stopTransport(transport,{schedule:(fn,delay)=>{timers.set(++key,{fn,delay});return key;},cancel:id=>timers.delete(id)});const rejected=assert.rejects(work,/did not close after cancellation/);[...timers.values()].find(t=>t.delay===2000).fn();await rejected;assert.equal(transport.process,child);assert.equal(transport.closed,false);assert.equal(timers.size,0);
});

test('unsettled startup has a bounded cleanup error instead of being abandoned',async()=>{
 let release;const pending=new Promise(resolve=>{release=resolve;});const timers=new Map();let key=0;
 const cleanup=settleStartup(pending,{schedule:(fn,delay)=>{assert.equal(delay,2000);timers.set(++key,fn);return key;},cancel:id=>timers.delete(id)});
 const rejected=assert.rejects(cleanup,/startup did not settle after transport cancellation/);timers.values().next().value();await rejected;assert.equal(timers.size,0);release();await pending;
});
