import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { withBrowserContext, screenshotPaths } from "./browser-context.mjs";

test("browser profile cleanup covers launch failures and preserves primary failures", async () => {
  let path;
  const primary = Error("synthetic launch failure");
  await assert.rejects(withBrowserContext({ launchPersistentContext: async profile => { path = profile; throw primary; } }, "mdbx-unit-", {}, () => {}), error => error === primary);
  assert.equal(existsSync(path), false);
  const workFailure = Error("synthetic work failure"), closeFailure = Error("synthetic close failure");
  const fake = { launchPersistentContext: async profile => { path = profile; return { close: async () => { throw closeFailure; } }; } };
  await assert.rejects(withBrowserContext(fake, "mdbx-unit-", {}, async () => { throw workFailure; }), error => error === workFailure);
  assert.equal(existsSync(path), false);
  await assert.rejects(withBrowserContext(fake, "mdbx-unit-", {}, async () => {}), error => error === closeFailure);
  assert.equal(existsSync(path), false);
});

test("screenshot paths remain distinct for all accepted filename shapes", () => {
  for (const path of ["shot.png", "shot.PNG", "shot.jpeg", "shot"]) {
    const paths = screenshotPaths(path);
    assert.equal(new Set(Object.values(paths)).size, 3);
  }
});
