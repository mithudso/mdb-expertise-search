// End-to-end check in real Chromium (opt-in; needs Playwright and its Chromium):
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs node test/e2e.mjs [screenshot.png]
//
// Loads the unpacked extension, then checks:
//  1. grabSelection() reads a highlighted <pre> and the selected part of a <textarea> in a real page;
//  2. the right-click handoff (a unique chrome.storage.session handoff) reaches the popup and renders a report;
//  3. "Try an example" renders log evidence, findings and an index recommendation;
//  4. "Copy as Markdown" writes the case note to the clipboard.
// Toolbar clicks cannot be automated, so the popup is opened as a tab (popup.html#tab).
import assert from "node:assert/strict";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { withBrowserContext, screenshotPaths } from "./browser-context.mjs";
import { grabSelection } from "../lib/capture.js";

const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const extDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const shot = process.argv[2];

const LOG = '{"t":{"$date":"2026-10-14T09:12:44Z"},"msg":"Slow query","attr":{"ns":"shop.orders","command":' +
  '{"find":"orders","filter":{"status":{"$ne":"x"},"name":{"$regex":"smith"}},"sort":{"ts":-1},"$db":"shop"},' +
  '"planSummary":"COLLSCAN","docsExamined":50000,"nreturned":5,"durationMillis":900}}';

let appSkipped = false;
await withBrowserContext(chromium, "mql-ext-", {
  headless: true,
  channel: "chromium", // full Chromium in new-headless mode; the headless shell cannot run extensions
  args: [`--disable-extensions-except=${extDir}`, `--load-extension=${extDir}`],
  permissions: ["clipboard-read", "clipboard-write"],
  viewport: { width: 900, height: 1000 },
}, async ctx => {
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker", { timeout: 15000 });
  const extId = new URL(sw.url()).host;
  console.log(`extension loaded: ${extId}`);

  // 1. selection capture in a real page
  const page = await ctx.newPage();
  await page.setContent(`<pre id="log">${LOG.replace(/</g, "&lt;")}</pre>
    <textarea id="ta">noise before db.c.find({ a: /x/ }) noise after</textarea>`);
  const fn = `(${grabSelection.toString()})()`;
  await page.evaluate(() => {
    const r = document.createRange();
    r.selectNodeContents(document.getElementById("log"));
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  });
  assert.equal(await page.evaluate(fn), LOG, "highlighted <pre> text");
  await page.evaluate(() => {
    const ta = document.getElementById("ta");
    ta.focus();
    ta.setSelectionRange(13, 34);
  });
  assert.equal(await page.evaluate(fn), "db.c.find({ a: /x/ })", "textarea selection");
  console.log("ok  grabSelection: <pre> highlight and textarea selection");

  // 2. right-click handoff -> popup
  await sw.evaluate(async (text) => chrome.storage.session.set({ "selectionHandoff:popup-test": { text, ts: Date.now() } }), LOG);
  const popup = await ctx.newPage();
  await popup.goto(`chrome-extension://${extId}/popup.html#tab?handoff=popup-test`);
  await popup.waitForSelector("#result:not([hidden]) .summary", { timeout: 10000 });
  const status = await popup.textContent("#status");
  assert.match(status, /right-click selection/);
  const body = await popup.textContent("#result");
  assert.match(body, /slow-query log line/);
  assert.match(body, /COLLSCAN/);
  assert.match(body, /log-collscan/);
  assert.match(body, /unanchored-regex/);
  assert.match(body, /db\.orders\.createIndex/);
  assert.equal(await sw.evaluate(async () => (await chrome.storage.session.get("selectionHandoff:popup-test"))["selectionHandoff:popup-test"]), undefined,
    "handoff is consumed");
  console.log("ok  context-menu handoff renders the report and is consumed");

  // 3. example button (inside the collapsed editor)
  assert.equal(await popup.evaluate(() => document.getElementById("input-section").open), false,
    "editor collapsed when a query was recognised");
  await popup.click("#input-label");
  await popup.click("#example");
  await popup.waitForFunction(() => document.getElementById("status").textContent.includes("example"));
  assert.match(await popup.textContent("#result"), /scanned : returned/);
  console.log("ok  'Try an example' renders evidence, findings, indexes");

  // 4. copy as Markdown
  await popup.click("text=Copy as Markdown for the case");
  await popup.waitForFunction(() => [...document.querySelectorAll("button")].some(button => button.textContent === "Copied"));
  const clip = await popup.evaluate(() => navigator.clipboard.readText());
  assert.match(clip, /^\*\*MQL optimizer \(static review\)\*\*/);
  assert.match(clip, /\[MongoDB docs\]\(https:\/\/www\.mongodb\.com\/docs\//);
  console.log("ok  Copy as Markdown puts the case note on the clipboard");

  if (shot) {
    await popup.setViewportSize({ width: 600, height: 1110 });
    await popup.evaluate(() => { document.body.style.maxHeight = "none"; });
    await popup.screenshot({ path: shot });
    console.log(`screenshot: ${shot}`);
  }

  // 5. popup: a selection that is not a query searches the corpus instead (needs packaged data/)
  // An unavailable optional file is a skip; evaluation failures propagate and fail the script.
  const hasData = await sw.evaluate(async () => {
    try { return (await fetch(chrome.runtime.getURL("data/meta.json"))).ok; }
    catch { return false; }
  });
  if (!hasData) {
    appSkipped = true;
    console.log("skip app checks: no data/ packaged (run scripts/package_chrome_extension.py)");
  } else {
    await sw.evaluate(async () => chrome.storage.session.set({ "selectionHandoff:search-test": { text: "shard key jumbo chunks balancer", ts: Date.now() } }));
    const pop2 = await ctx.newPage();
    await pop2.goto(`chrome-extension://${extId}/popup.html#tab?handoff=search-test`);
    await pop2.waitForSelector(".hits li", { timeout: 15000 });
    assert.ok((await pop2.locator(".hits li").count()) >= 1);
    assert.match(await pop2.textContent("#result"), /MongoDB expertise/);
    console.log("ok  popup: non-query selection shows corpus passages");

    // 6. app search, facets, document view
    const app = await ctx.newPage();
    await app.setViewportSize({ width: 1400, height: 900 });
    await app.goto(`chrome-extension://${extId}/app.html#search?q=${encodeURIComponent("shard key jumbo chunks")}`);
    await app.waitForSelector("#results li", { timeout: 20000 });
    const n = await app.locator("#results li").count();
    assert.ok(n >= 5, `results: ${n}`);
    assert.match(await app.textContent("#search-status"), /results? in \d+ ms/);
    assert.ok((await app.locator("#detail .md").count()) === 1, "detail pane shows the first passage");
    assert.ok((await app.locator("#sources li").count()) > 20, "area facets listed");
    const source = await app.locator("#results li .src").first().textContent();
    await app.locator("#sources li").filter({ has: app.locator(".name", { hasText: source }) }).first().click();
    await app.waitForFunction(() => /area /.test(document.getElementById("search-status").textContent));
    assert.ok((await app.locator("#results li .src").allTextContents()).every(value => value === source), "every filtered hit belongs to the chosen source");
    console.log(`ok  app search: ${n} results, detail pane, ${await app.locator("#sources li").count()} area facets, facet narrowing`);
    await app.click("text=Open document");
    await app.waitForSelector("#tab-doc:not([hidden]) .chunk.target", { timeout: 10000 });
    assert.match(await app.textContent("#doc-title"), /\.(md|txt) · /);
    console.log("ok  document view opens at the passage");

    // 7. recipes, lint, operators, about
    await app.goto(`chrome-extension://${extId}/app.html#recipes`);
    await app.waitForSelector("#recipes li");
    const recipes = await app.locator("#recipes li").count();
    assert.ok(recipes >= 20, `recipes: ${recipes}`);
    await app.goto(`chrome-extension://${extId}/app.html#lint`);
    await app.click("#lint-run");
    await app.waitForSelector("#lint-out .diag");
    assert.match(await app.textContent("#lint-out"), /unknown-operator/);
    await app.goto(`chrome-extension://${extId}/app.html#operators`);
    const operatorCount = await app.locator("#ops li").count();
    await app.fill("#op-filter", "$lookup");
    assert.ok((await app.locator("#ops li").count()) < operatorCount, "operator filter removes nonmatching rows");
    assert.match(await app.textContent("#ops"), /\$lookup/);
    await app.goto(`chrome-extension://${extId}/app.html#about`);
    await app.waitForFunction(() => /Passages/.test(document.getElementById("stats").textContent));
    console.log(`ok  recipes (${recipes}), lint diagnostics, operator lookup, about stats`);

    // 8. optimizer "read more" opens the corpus page; right-click lint handoff
    await app.goto(`chrome-extension://${extId}/app.html#optimize`);
    await app.click("#opt-example");
    await app.click("text=Read more in the corpus >> nth=0");
    await app.waitForSelector("#tab-doc:not([hidden]) .chunk", { timeout: 10000 });
    console.log("ok  optimizer 'Read more in the corpus' opens the reference in the app");
    const lintText = "db.c.find({ synthetic: { $gtt: 1 } })";
    await sw.evaluate(async text => chrome.storage.session.set({ "selectionHandoff:lint-test": { tab: "lint", text, ts: Date.now() } }), lintText);
    const app2 = await ctx.newPage();
    await app2.goto(`chrome-extension://${extId}/app.html#lint?handoff=lint-test`);
    await app2.waitForSelector("#lint-out .diag");
    assert.equal(await app2.inputValue("#lint-input"), lintText);
    assert.equal(await sw.evaluate(async () => (await chrome.storage.session.get("selectionHandoff:lint-test"))["selectionHandoff:lint-test"]), undefined);
    console.log("ok  right-click lint handoff");

    if (shot) {
      await app.goto(`chrome-extension://${extId}/app.html#search?q=${encodeURIComponent("why is my compound index not used for sort")}`);
      await app.waitForSelector("#results li");
      const appShot = screenshotPaths(shot).app;
      await app.screenshot({ path: appShot });
      await pop2.setViewportSize({ width: 600, height: 760 });
      await pop2.screenshot({ path: screenshotPaths(shot).search });
      console.log(`screenshot: ${appShot}`);
    }
  }
 });
console.log(appSkipped ? "e2e: popup checks passed; app checks skipped (no packaged data)" : "e2e: all checks passed");
