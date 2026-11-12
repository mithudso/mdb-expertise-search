"use strict";
const vscode = require("vscode");
const { LanguageClient, CloseAction } = require("vscode-languageclient/node");
const { resolveServerCommand } = require("./server-path");
const { spawnTransport, stopTransport, settleStartup } = require("./server-process");

let client;
let active = false;
let transition = Promise.resolve();

function serialize(work) {
  const next = transition.then(work);
  transition = next.catch(() => {});
  return next;
}

// LanguageClient v9 rejects dispose during Starting. Own its child transport so cancellation can
// settle initialization first, then use the protected close hook and ordinary disposal for cleanup.
class OwnedLanguageClient extends LanguageClient {
  constructor(record, ...args) { super(...args); this.record = record; }
  start() {
    const pending = super.start();
    const record = this.record;
    record.startPending = pending;
    pending.then(() => {
      if (record.startPending === pending) { record.startPending = null; record.startFailed = false; }
    }, () => {
      if (record.startPending === pending) { record.startPending = null; record.startFailed = true; }
    });
    return pending;
  }
  handleConnectionClosed() {
    const pending = super.handleConnectionClosed();
    this.record.closeHandling = pending;
    return pending;
  }
  async dispose(timeout) {
    const record = this.record;
    const pending = record.startPending;
    if (pending || record.startFailed) {
      await stopTransport(record.transport);
      // A timeout keeps this record owned and prevents replacement; a late start is never abandoned.
      if (pending) await settleStartup(pending);
      if (record.closeHandling) await record.closeHandling;
      // A rejected initialization is StartFailed. The close hook retires its registered features
      // and reaches Stopped without sending an invalid shutdown request to an uninitialized server.
      if (!this.isRunning()) await super.handleConnectionClosed();
    }
    await super.dispose(timeout);
    await stopTransport(record.transport);
  }
}

async function stopClient(resolveCancellation = true) {
  const outgoing = client;
  if (!outgoing) return;
  outgoing.cancelled = true;
  await outgoing.value.dispose();
  if (resolveCancellation) outgoing.finishCancellation();
  if (client === outgoing) client = undefined;
}

function startClient() {
  if (!active) return null;
  const cfg = vscode.workspace.getConfiguration("mql");
  const workspaces = vscode.workspace.workspaceFolders || [];
  const folders = workspaces.map(f => f.uri.fsPath);
  const command = resolveServerCommand(cfg.get("server.path"), folders);
  const args = cfg.get("server.args") || [];
  const cwd = workspaces[0]?.uri.scheme === "file" ? workspaces[0].uri.fsPath : undefined;
  let finishCancellation;
  const cancelled = new Promise(resolve => { finishCancellation = resolve; });
  const record = { cancelled: false, transport: null, startPending: null, startFailed: false, closeHandling: null, finishCancellation };
  const serverOptions = async () => {
    if (record.cancelled) throw new Error("MQL startup cancelled");
    // An automatic restart must retire the preceding owned child before replacing its handle.
    await stopTransport(record.transport);
    if (record.cancelled) throw new Error("MQL startup cancelled");
    const transport = spawnTransport(command, args, cwd);
    record.transport = transport;
    return transport.ready;
  };
  let defaultErrors;
  const clientOptions = {
    documentSelector: [{ scheme: "file", language: "mql" }, { scheme: "untitled", language: "mql" }],
    outputChannelName: "MQL Language Server",
    errorHandler: {
      error: (...values) => defaultErrors.error(...values),
      closed: () => record.cancelled ? { action: CloseAction.DoNotRestart, handled: true } : defaultErrors.closed(),
    },
  };
  const value = new OwnedLanguageClient(record, "mql", "MQL Language Server", serverOptions, clientOptions);
  record.value = value;
  defaultErrors = value.createDefaultErrorHandler?.();
  client = record;
  const started = Promise.resolve().then(() => value.start()).catch(async () => {
    if (record.cancelled) return;
    await serialize(async () => { if (client === record) await stopClient(false); });
    vscode.window.showErrorMessage("MQL: could not start the language server. Install the lsp extra or set mql.server.path.");
  });
  record.ready = Promise.race([started, cancelled]);
  return record;
}

async function activate(context) {
  active = true;
  context.subscriptions.push(
    { dispose: () => deactivate() },
    vscode.commands.registerCommand("mql.restartServer", async () => {
      const next = await serialize(async () => { await stopClient(); return startClient(); });
      await next?.ready;
    })
  );
  const next = await serialize(startClient);
  await next?.ready;
}

async function deactivate() {
  active = false;
  await serialize(stopClient);
}

module.exports = { activate, deactivate };
