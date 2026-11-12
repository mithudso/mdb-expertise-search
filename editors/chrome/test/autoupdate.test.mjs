// Auto-update: build identity, reload decision, and the alarm-driven check against a fake chrome API.
import { test } from "node:test";
import assert from "node:assert/strict";

import { ALARM, buildId, readBuild, shouldReload, startAutoUpdate, SESSION_KEY } from "../lib/autoupdate.js";

test("buildId prefers the commit, falls back to version@built_at, empty when nothing is known", () => {
  assert.equal(buildId({ commit: "abc123", version: "0.3.0" }), "abc123");
  assert.equal(buildId({ commit: "unknown", version: "0.3.0", built_at: "2026-10-20T00:00:00Z" }), "0.3.0@2026-10-20T00:00:00Z");
  assert.equal(buildId({ version: "0.3.0" }), "0.3.0@");
  assert.equal(buildId(null), "");
  assert.equal(buildId({}), "");
});

test("shouldReload only when both ids are known and differ", () => {
  assert.equal(shouldReload("a", "b"), true);
  assert.equal(shouldReload("a", "a"), false);
  assert.equal(shouldReload("", "b"), false);
  assert.equal(shouldReload("a", ""), false);
});

test("readBuild tolerates a missing file and non-OK responses", async () => {
  const runtime = { getURL: (p) => `chrome-extension://x/${p}` };
  assert.equal(await readBuild(async () => ({ ok: false }), runtime), null);
  assert.equal(await readBuild(async () => { throw new Error("nope"); }, runtime), null);
  assert.deepEqual(await readBuild(async (url, options) => {
    assert.equal(url, "chrome-extension://x/data/build.json");
    assert.deepEqual(options, { cache: "no-store" });
    return { ok: true, json: async () => ({ commit: "c1" }) };
  }, runtime), { commit: "c1" });
});

function fakeChrome(builds) {
  let i = 0;
  const session = {};
  const listeners = [];
  const created = [];
  const api = {
    alarms: { get: async () => null, create: (name, opts) => created.push([name, opts]), onAlarm: { addListener: (fn) => listeners.push(fn) } },
    runtime: { getURL: (p) => `ext://${p}`, reloaded: 0, reload() { this.reloaded += 1; } },
    storage: {
      session: {
        async get(k) { return { [k]: session[k] }; },
        async set(obj) { Object.assign(session, obj); },
        async remove(k) { delete session[k]; },
      },
    },
  };
  const fetchImpl = async () => {
    const b = builds[Math.min(i, builds.length - 1)];
    i += 1;
    return b ? { ok: true, json: async () => b } : { ok: false };
  };
  return { api, fetchImpl, listeners, created, session };
}

test("startAutoUpdate remembers the starting build and reloads once it changes", async () => {
  const { api, fetchImpl, listeners, created, session } = fakeChrome([
    { commit: "c1" }, // remember() at start
    { commit: "c1" }, // first check: unchanged
    { commit: "c2" }, // second check: new build
  ]);
  const handlers = startAutoUpdate(api, fetchImpl);
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(created[0][0], ALARM);
  assert.equal(session[SESSION_KEY], "c1");
  assert.equal(await handlers.check(), false);
  assert.equal(api.runtime.reloaded, 0);
  // the alarm listener drives the same check
  await listeners[0]({ name: "other" });
  assert.equal(api.runtime.reloaded, 0);
  await listeners[0]({ name: ALARM });
  assert.equal(api.runtime.reloaded, 1);
  assert.equal(session[SESSION_KEY], undefined, "stored id cleared so the new worker re-reads it");
});

test("startAutoUpdate is a no-op without the alarms API (e.g. a plain page context)", () => {
  assert.equal(startAutoUpdate({ runtime: {}, storage: {} }, async () => ({ ok: false })), null);
});

test("a build without data/build.json never reloads", async () => {
  const { api, fetchImpl } = fakeChrome([null, null, null]);
  const handlers = startAutoUpdate(api, fetchImpl);
  assert.equal(await handlers.check(), false);
  assert.equal(api.runtime.reloaded, 0);
});

test("worker restart preserves the baseline and existing alarm schedule", async () => {
  const { api, fetchImpl, session, created } = fakeChrome([{ commit: "new" }]);
  session[SESSION_KEY] = "old";
  const lookups = [];
  api.alarms.get = async name => { lookups.push(name); return { name, scheduledTime: 123 }; };
  const handlers = startAutoUpdate(api, fetchImpl);
  await handlers.ready;
  assert.equal(session[SESSION_KEY], "old");
  assert.deepEqual(lookups, [ALARM]);
  assert.deepEqual(created, []);
  assert.equal(await handlers.check(), true);
});

test("reload waits for deferred baseline removal and concurrent checks reload once", { timeout: 1000 }, async () => {
  const { api, fetchImpl, session } = fakeChrome([{ commit: "new" }]);
  session[SESSION_KEY] = "old";
  let release, started;
  const removing = new Promise(resolve => { started = resolve; });
  const gate = new Promise(resolve => { release = resolve; });
  api.storage.session.remove = async key => { started(); await gate; delete session[key]; };
  api.runtime.reload = () => { assert.equal(session[SESSION_KEY], undefined); api.runtime.reloaded++; };
  const handlers = startAutoUpdate(api, fetchImpl);
  const first = handlers.check(), second = handlers.check();
  await removing;
  assert.equal(api.runtime.reloaded, 0);
  release();
  assert.equal(await first, true);
  assert.equal(await second, false);
  assert.equal(api.runtime.reloaded, 1);
});

test("automatic startup and alarm failures are contained and the baseline can retry", async () => {
  const { api, fetchImpl, session, listeners } = fakeChrome([{ commit: "new" }]);
  session[SESSION_KEY] = "old";
  api.alarms.get = async () => { throw Error("synthetic alarm failure"); };
  let failing = true;
  api.storage.session.get = async key => { if (failing) throw Error("synthetic storage failure"); return { [key]: session[key] }; };
  const handlers = startAutoUpdate(api, fetchImpl);
  await handlers.ready;
  assert.equal(await listeners[0]({ name: ALARM }), false);
  assert.equal(session[SESSION_KEY], "old");
  failing = false;
  assert.equal(await handlers.check(), true);
});
