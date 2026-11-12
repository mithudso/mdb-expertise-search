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
  assert.strictEqual(new RegExp(template.patterns[0].match).test('\\\\' + String.fromCharCode(96)), true);
});

test('overlapping restarts and deactivation serialize client ownership', async () => {
  const Module = require('node:module');
  const originalLoad = Module._load;
  let restart, alive = 0, maxAlive = 0, disposed = 0;
  const clients = [];
  const tick = () => new Promise(resolve => setImmediate(resolve));
  class Client {
    constructor() { clients.push(this); }
    async start() { alive++; maxAlive = Math.max(maxAlive, alive); await tick(); }
    async dispose() { await tick(); alive--; disposed++; }
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
    assert.strictEqual(alive, 1);
    assert.strictEqual(maxAlive, 1);
    assert.strictEqual(context.subscriptions.length, 2);
    const pending = restart();
    await Promise.all([pending, extension.deactivate()]);
    assert.strictEqual(alive, 0);
    assert.strictEqual(disposed, clients.length);
  } finally {
    Module._load = originalLoad;
    delete require.cache[filename];
  }
});
