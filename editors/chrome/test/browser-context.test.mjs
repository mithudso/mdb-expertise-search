import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { withBrowserContext, screenshotPaths } from "./browser-context.mjs";

test("browser profile cleanup covers launch failures and preserves primary failures", async () => {
  let path, closes = 0;
  const primary = Error("synthetic launch failure");
  await assert.rejects(withBrowserContext({ launchPersistentContext: async profile => { path = profile; throw primary; } }, "mdbx-unit-", {}, () => {}), error => error === primary);
  assert.equal(existsSync(path), false);
  const workFailure = Error("synthetic work failure"), closeFailure = Error("synthetic close failure");
  const fake = { launchPersistentContext: async profile => { path = profile; return { close: async () => { closes++; throw closeFailure; } }; } };
  await assert.rejects(withBrowserContext(fake, "mdbx-unit-", {}, async () => { throw workFailure; }), error => error === workFailure);
  assert.equal(existsSync(path), false);
  assert.equal(closes, 1);
  await assert.rejects(withBrowserContext(fake, "mdbx-unit-", {}, async () => {}), error => error === closeFailure);
  assert.equal(closes, 2);
  assert.equal(existsSync(path), false);
});

test("screenshot paths remain distinct for all accepted filename shapes", () => {
  for (const path of ["shot.png", "shot.PNG", "shot.jpeg", "shot"]) {
    const paths = screenshotPaths(path);
    const dot = path.lastIndexOf(".");
    const name = dot < 0 ? path : path.slice(0, dot), ext = dot < 0 ? ".png" : path.slice(dot);
    assert.deepEqual(paths, { popup: path, app: `${name}-app${ext}`, search: `${name}-popup-search${ext}` });
  }
});

for (const reason of [0, false, null, undefined]) test(`falsy rejection ${String(reason)} preserves primary and cleanup outcomes`, async () => {
  const outcome = promise => promise.then(value => ({ fulfilled: true, value }), value => ({ fulfilled: false, value }));
  const chromium = { launchPersistentContext: async () => ({ close: async () => { throw reason; } }) };
  assert.deepEqual(await outcome(withBrowserContext(chromium, "mdbx-falsy-", {}, async () => "ok")), { fulfilled: false, value: reason });
  const cleanup = { launchPersistentContext: async () => ({ close: async () => { throw Error("cleanup"); } }) };
  assert.deepEqual(await outcome(withBrowserContext(cleanup, "mdbx-falsy-", {}, async () => { throw reason; })), { fulfilled: false, value: reason });
});
