'use strict';
const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');
const { resolveServerCommand } = require('./server-path');

let client;

async function startClient(context) {
  const cfg = vscode.workspace.getConfiguration('mql');
  const folders = (vscode.workspace.workspaceFolders || []).map((f) => f.uri.fsPath);
  const command = resolveServerCommand(cfg.get('server.path'), folders);
  const args = cfg.get('server.args') || [];
  const serverOptions = { command, args, transport: TransportKind.stdio };
  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'mql' }, { scheme: 'untitled', language: 'mql' }],
    outputChannelName: 'MQL Language Server',
  };
  client = new LanguageClient('mql', 'MQL Language Server', serverOptions, clientOptions);
  context.subscriptions.push(client);
  try {
    await client.start();
  } catch (err) {
    vscode.window.showErrorMessage(
      `MQL: could not start "${command}". Install it with \`pip install -e '.[lsp]'\` or set mql.server.path. (${err.message})`
    );
  }
}

async function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand('mql.restartServer', async () => {
      if (client) await client.stop();
      await startClient(context);
    })
  );
  await startClient(context);
}

async function deactivate() {
  if (client) await client.stop();
}

module.exports = { activate, deactivate };
