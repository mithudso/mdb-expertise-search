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
  const pkg = require('../package.json');
  const g = require('../syntaxes/mql.tmLanguage.json');
  require('../language-configuration.json');
  assert.strictEqual(pkg.contributes.grammars[0].scopeName, g.scopeName);
  assert.ok(pkg.activationEvents.includes('onLanguage:mql'));
  for (const f of ['extension.js', 'server-path.js']) assert.ok(require('node:fs').existsSync(path.join(__dirname, '..', f)));
});
