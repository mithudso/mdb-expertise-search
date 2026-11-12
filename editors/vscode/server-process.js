"use strict";
const { spawn } = require("node:child_process");

// The returned handle owns exactly this child, including failed spawn and delayed close events.
function spawnTransport(command, args, cwd, spawnImpl = spawn) {
  const process = spawnImpl(command, [...args, "--stdio"], { cwd, stdio: "pipe" });
  let closed = false, spawning = true, resolveClosed;
  const completion = new Promise(resolve => { resolveClosed = resolve; });
  const ready = new Promise((resolve, reject) => {
    process.once("spawn", () => { spawning = false; resolve(process); });
    process.once("error", error => { spawning = false; reject(error); });
  });
  // A spawn error has no running process. Node still emits close after the error.
  ready.catch(() => {});
  process.once("close", () => { closed = true; resolveClosed(); });
  return { process, ready, completion, get closed() { return closed; }, get spawning() { return spawning; } };
}

async function stopTransport(transport, { schedule = setTimeout, cancel = clearTimeout } = {}) {
  if (!transport || transport.closed) return;
  const child = transport.process;
  const terminate = signal => {
    if (!transport.closed && child.pid !== undefined) child.kill(signal);
  };
  // A request may arrive before Node reports the spawn. Keep cancellation attached to that event.
  const onSpawn = () => terminate("SIGTERM");
  child.once("spawn", onSpawn);
  let escalation, deadline;
  const timeout = new Promise((_resolve, reject) => {
    escalation = schedule(() => terminate("SIGKILL"), 500);
    deadline = schedule(() => reject(new Error("MQL server transport did not close after cancellation")), 2000);
  });
  try {
    terminate("SIGTERM");
    await Promise.race([transport.completion, timeout]);
  } finally {
    child.removeListener("spawn", onSpawn);
    cancel(escalation); cancel(deadline);
  }
}

async function settleStartup(pending, { schedule = setTimeout, cancel = clearTimeout } = {}) {
  let timer;
  try {
    await Promise.race([pending.catch(() => {}), new Promise((_resolve, reject) => {
      timer = schedule(() => reject(new Error("MQL startup did not settle after transport cancellation")), 2000);
    })]);
  } finally { cancel(timer); }
}

module.exports = { spawnTransport, stopTransport, settleStartup };
