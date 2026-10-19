// End-to-end check in real Chromium (opt-in; needs Playwright and its Chromium):
//
//   PLAYWRIGHT=/path/to/node_modules/playwright node test/e2e.mjs [screenshot.png]
//
// Loads the unpacked extension, then checks:
//  1. grabSelection() reads a highlighted <pre> and the selected part of a <textarea> in a real page;
//  2. the right-click handoff (chrome.storage.session "pending") reaches the popup and renders a report;
//  3. "Try an example" renders log evidence, findings and an index recommendation;
//  4. "Copy as Markdown" writes the case note to the clipboard.
// Toolbar clicks cannot be automated, so the popup is opened as a tab (popup.html#tab).
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { grabSelection } from "../lib/capture.js";

const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const extDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const profile = mkdtempSync(join(tmpdir(), "mql-ext-"));
const shot = process.argv[2];

const LOG = '{"t":{"$date":"2026-10-14T09:12:44Z"},"msg":"Slow query","attr":{"ns":"shop.orders","command":' +
  '{"find":"orders","filter":{"status":{"$ne":"x"},"name":{"$regex":"smith"}},"sort":{"ts":-1},"$db":"shop"},' +
  '"planSummary":"COLLSCAN","docsExamined":50000,"nreturned":5,"durationMillis":900}}';

const ctx = await chromium.launchPersistentContext(profile, {
  headless: true,
  channel: "chromium", // full Chromium in new-headless mode; the headless shell cannot run extensions
  args: [`--disable-extensions-except=${extDir}`, `--load-extension=${extDir}`],
  permissions: ["clipboard-read", "clipboard-write"],
  viewport: { width: 900, height: 1000 },
});
let ok = false;
try {
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
  await sw.evaluate(async (text) => chrome.storage.session.set({ pending: { text, ts: Date.now() } }), LOG);
  const popup = await ctx.newPage();
  await popup.goto(`chrome-extension://${extId}/popup.html#tab`);
  await popup.waitForSelector("#result:not([hidden]) .summary", { timeout: 10000 });
  const status = await popup.textContent("#status");
  assert.match(status, /right-click selection/);
  const body = await popup.textContent("#result");
  assert.match(body, /slow-query log line/);
  assert.match(body, /COLLSCAN/);
  assert.match(body, /log-collscan/);
  assert.match(body, /unanchored-regex/);
  assert.match(body, /db\.orders\.createIndex/);
  assert.equal(await sw.evaluate(async () => (await chrome.storage.session.get("pending")).pending), undefined,
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
  ok = true;
} finally {
  await ctx.close();
  rmSync(profile, { recursive: true, force: true });
}
console.log(ok ? "e2e: all checks passed" : "e2e: FAILED");
process.exit(ok ? 0 : 1);
