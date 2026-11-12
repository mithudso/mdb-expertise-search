'use strict';
const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');
const { resolveServerCommand } = require('./server-path');

let client;
let active = false;
let transition = Promise.resolve();

function serialize(work) {
  const next = transition.then(work);
  transition = next.catch(() => {});
  return next;
}

async function stopClient() {
  const outgoing = client;
  client = undefined;
  if (outgoing) await outgoing.dispose();
}

async function startClient() {
  if (!active) return;
  const cfg = vscode.workspace.getConfiguration('mql');
  const folders = (vscode.workspace.workspaceFolders || []).map((f) => f.uri.fsPath);
  const command = resolveServerCommand(cfg.get('server.path'), folders);
  const args = cfg.get('server.args') || [];
  const serverOptions = { command, args, transport: TransportKind.stdio };
  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'mql' }, { scheme: 'untitled', language: 'mql' }],
    outputChannelName: 'MQL Language Server',
  };
  const next = new LanguageClient('mql', 'MQL Language Server', serverOptions, clientOptions);
  client = next;
  try {
    await next.start();
  } catch (err) {
    if (client === next) client = undefined;
    await next.dispose();
    vscode.window.showErrorMessage('MQL: could not start the language server. Install the lsp extra or set mql.server.path.');
  }
}

async function activate(context) {
  active = true;
  context.subscriptions.push(
    { dispose: () => deactivate() },
    vscode.commands.registerCommand('mql.restartServer', () => serialize(async () => {
      await stopClient();
      await startClient();
    }))
  );
  await serialize(startClient);
}

async function deactivate() {
  active = false;
  await serialize(stopClient);
}

module.exports = { activate, deactivate };
