'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { resolveServerCommand } = require('../server-path');

test('explicit setting wins', () => {
  assert.strictEqual(resolveServerCommand(' /opt/mql-lsp ', ['/w'], 'linux', () => true), '/opt/mql-lsp');
});
test('workspace venv is used when present', () => {
  const want = path.join('/w', '.venv', 'bin', 'mql-lsp');
  assert.strictEqual(resolveServerCommand('', ['/other', '/w'], 'linux', (p) => p === want), want);
});
test('windows venv layout', () => {
  const want = path.join('C:\\w', '.venv', 'Scripts', 'mql-lsp.exe');
  assert.strictEqual(resolveServerCommand('', ['C:\\w'], 'win32', (p) => p === want), want);
});
test('falls back to PATH', () => {
  assert.strictEqual(resolveServerCommand('', ['/w'], 'linux', () => false), 'mql-lsp');
  assert.strictEqual(resolveServerCommand(undefined, undefined, 'linux', () => false), 'mql-lsp');
});
test('manifest and grammar are valid JSON and consistent', () => {
  const fs = require('node:fs');
  const pkg = require('../package.json');
  const root = path.join(__dirname, '..');
  assert.ok(fs.statSync(path.resolve(root, pkg.main)).isFile());
  const grammar = pkg.contributes.grammars.find(g => g.language === 'mql');
  const g = JSON.parse(fs.readFileSync(path.resolve(root, grammar.path), 'utf8'));
  const language = pkg.contributes.languages.find(l => l.id === 'mql');
  JSON.parse(fs.readFileSync(path.resolve(root, language.configuration), 'utf8'));
  assert.strictEqual(grammar.scopeName, g.scopeName);
  assert.ok(pkg.activationEvents.includes('onLanguage:mql'));
});

test('grammar matches whole methods, quoted dollar forms and numeric boundaries', () => {
  const grammar = require('../syntaxes/mql.tmLanguage.json');
  const rules = grammar.repository.value.patterns;
  const firstMatch = source => rules.find(r => r.match && new RegExp(r.match).test(source));
  for (const [source, scope] of [
    ['"$match": {}', 'keyword.operator.mql'],
    ['"$$ROOT"', 'variable.language.system.mql'],
    ['"$nested.value"', 'variable.other.field-path.mql'],
  ]) {
    const rule = firstMatch(source);
    assert.strictEqual(rule.captures?.[2]?.name, scope);
    assert.ok(rules.indexOf(rule) < rules.findIndex(r => r.begin === '"'));
  }
  const method = grammar.repository['statement-words'].patterns.find(r => r.captures);
  const matched = new RegExp(method.match).exec('db.c.findOne({})');
  assert.strictEqual(matched[3], 'findOne');
  const numeric = rules.find(r => r.name === 'constant.numeric.mql');
  assert.strictEqual(new RegExp(numeric.match).test('field2'), false);
  for (const value of ['-2.5', '0x10', '1e3', '.25']) assert.strictEqual(new RegExp(numeric.match).exec(value)[0], value);
  const template = rules.find(r => r.name === 'string.template.mql');
  const escapedBacktick = String.fromCharCode(92, 96);
  assert.strictEqual(new RegExp(template.patterns[0].match).exec(escapedBacktick)?.[0], escapedBacktick);
});

test('overlapping restarts and deactivation serialize client ownership', async () => {
  const Module = require('node:module');
  const originalLoad = Module._load;
  let restart, maxAlive = 0;
  const live = new Set(), disposed = new Set();
  const clients = [];
  const tick = () => new Promise(resolve => setImmediate(resolve));
  class Client {
    constructor() { clients.push(this); }
    isRunning() { return live.has(this); }
    async start() { assert.ok(!live.has(this)); live.add(this); maxAlive = Math.max(maxAlive, live.size); await tick(); }
    async dispose() { await tick(); assert.ok(live.delete(this), "dispose owns a live client"); assert.ok(!disposed.has(this)); disposed.add(this); }
  }
  const vscode = {
    workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
    commands: { registerCommand: (name, callback) => { restart = callback; return { dispose() {} }; } },
    window: { showErrorMessage: () => assert.fail('unexpected start failure') },
  };
  const filename = require.resolve('../extension');
  try {
    Module._load = function(name, ...args) {
      if (name === 'vscode') return vscode;
      if (name === 'vscode-languageclient/node') return { LanguageClient: Client, TransportKind: { stdio: 0 } };
      return originalLoad.call(this, name, ...args);
    };
    delete require.cache[filename];
    const extension = require(filename), context = { subscriptions: [] };
    await extension.activate(context);
    await Promise.all([restart(), restart(), restart()]);
    assert.strictEqual(live.size, 1);
    assert.strictEqual(maxAlive, 1);
    assert.strictEqual(context.subscriptions.length, 2);
    const pending = restart();
    await Promise.all([pending, extension.deactivate()]);
    assert.strictEqual(live.size, 0);
    assert.strictEqual(disposed.size, clients.length);
  } finally {
    Module._load = originalLoad;
    delete require.cache[filename];
  }
});

test("automatic discovery skips directories and non-executable POSIX files", { skip: process.platform === "win32" }, () => {
  const fs = require("node:fs"), os = require("node:os");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mql-path-"));
  try {
    const workspaces = ["directory", "plain", "valid"].map(name => path.join(root, name));
    const candidates = workspaces.map(folder => path.join(folder, ".venv", "bin", "mql-lsp"));
    for (const candidate of candidates) fs.mkdirSync(path.dirname(candidate), { recursive: true });
    fs.mkdirSync(candidates[0]); fs.writeFileSync(candidates[1], "synthetic", {mode: 0o600});
    fs.writeFileSync(candidates[2], "synthetic", {mode: 0o700});
    assert.strictEqual(resolveServerCommand("", workspaces, "linux"), candidates[2]);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test("grammar uses identifier boundaries, complete method inventory and bounded ordinary strings", () => {
  const g = require("../syntaxes/mql.tmLanguage.json"), values = g.repository.value.patterns;
  const method = new RegExp(g.repository["statement-words"].patterns[2].match, "g");
  for (const name of ["replaceOne", "findOneAndDelete", "findOneAndReplace", "count", "getCollection"]) assert.ok([...`db.getCollection("c").${name}({})`.matchAll(method)].some(match => match[1] === name));
  const constant = new RegExp(values.find(r => r.name === "constant.language.mql").match);
  for (const value of ["true$flag", "$true"]) assert.strictEqual(constant.test(value), false);
  const keyword = new RegExp(g.repository["statement-words"].patterns[0].match);
  assert.strictEqual(keyword.test("$use"), false);
  const constructor = new RegExp(values.find(r => r.name === "support.class.constructor.mql").match);
  assert.strictEqual(constructor.test("my$Date()"), false);
  for (const name of ["Date", "ObjectId", "ISODate", "NumberLong"]) assert.strictEqual(constructor.test(name + "()"), true);
  for (const name of ["double", "single"]) {
    const rule = values.find(r => r.name === `string.quoted.${name}.mql`);
    assert.ok(new RegExp(rule.end).test("\n"));
    assert.strictEqual(new RegExp(rule.patterns[0].match).exec("\\\n")[0], "\\\n");
  }
  const regex = new RegExp(values.find(r => r.name === "string.regexp.mql").match);
  assert.strictEqual(regex.exec("/[/]/")[0], "/[/]/");
  assert.strictEqual(regex.test("/" + "[]".repeat(20) + "\\/"), false);
  const word = new RegExp(require("../language-configuration.json").wordPattern);
  for (const identifier of ["foo$bar", "$foo$bar", "$$foo$bar"]) assert.strictEqual(word.exec(identifier)[0], identifier);
});

test("a failed disposal retains ownership until a later restart retries it", async () => {
  const Module = require("node:module"), originalLoad = Module._load;
  const filename = require.resolve("../extension"); let restart, starts = 0, attempts = 0;
  const live = new Set();
  class Client {
    async start() { starts++; live.add(this); }
    async dispose() { if (++attempts === 1) throw Error("synthetic disposal"); assert.ok(live.delete(this)); }
  }
  const vscode = { workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
    commands: { registerCommand: (_name, callback) => { restart = callback; return { dispose() {} }; } },
    window: { showErrorMessage: () => assert.fail("unexpected start failure") } };
  try {
    Module._load = function(name, ...args) {
      if (name === "vscode") return vscode;
      if (name === "vscode-languageclient/node") return { LanguageClient: Client, TransportKind: { stdio: 0 } };
      return originalLoad.call(this, name, ...args);
    };
    delete require.cache[filename]; const extension = require(filename);
    await extension.activate({subscriptions: []});
    await assert.rejects(restart(), /synthetic disposal/); assert.strictEqual(starts, 1); assert.strictEqual(live.size, 1);
    await restart(); assert.strictEqual(starts, 2); assert.strictEqual(live.size, 1);
    await extension.deactivate(); assert.strictEqual(live.size, 0);
  } finally { Module._load = originalLoad; delete require.cache[filename]; }
});


test('non-string settings continue normal discovery', () => {
  for (const value of [true, 1, {}, []]) assert.strictEqual(resolveServerCommand(value, [], 'linux', () => false), 'mql-lsp');
});
test('direct database methods and system variable identifiers have exact scopes', () => {
  const grammar = require('../syntaxes/mql.tmLanguage.json');
  const db = new RegExp(grammar.repository['statement-words'].patterns[1].match);
  for (const name of ['watch', 'aggregate', 'getCollection']) assert.strictEqual(db.exec(`db.${name}()`)[2], undefined);
  assert.strictEqual(db.exec('db.orders.find({})')[2], 'orders');
  const system = new RegExp(grammar.repository.value.patterns.find(r => r.name === 'variable.language.system.mql').match);
  assert.strictEqual(system.test('$$ROOT'), true);
  for (const text of ['prefix$$ROOT', '$$ROOT$suffix', '$$$ROOT']) assert.strictEqual(system.test(text), false);
});
test('native directory rejection does not depend on POSIX executable bits', () => {
  const fs=require('node:fs'),os=require('node:os');const root=fs.mkdtempSync(path.join(os.tmpdir(),'synthetic-mql-native-'));
  try{const rel=process.platform==='win32'?['.venv','Scripts','mql-lsp.exe']:['.venv','bin','mql-lsp'];const candidate=path.join(root,...rel);fs.mkdirSync(candidate,{recursive:true});assert.strictEqual(resolveServerCommand('',[root]),'mql-lsp');}
  finally{fs.rmSync(root,{recursive:true,force:true});}
});
