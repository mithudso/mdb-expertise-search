// Debug helper: open app.html at a hash in real Chromium and print status, console messages and errors.
//   PLAYWRIGHT=/path/to/playwright/index.mjs node test/debug-app.mjs '#search?q=shard'
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const extDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const profile = mkdtempSync(join(tmpdir(), "mql-dbg-"));
const ctx = await chromium.launchPersistentContext(profile, { headless: true, channel: "chromium",
  args: [`--disable-extensions-except=${extDir}`, `--load-extension=${extDir}`] });
try {
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker", { timeout: 15000 });
  const id = new URL(sw.url()).host;
  const page = await ctx.newPage();
  page.on("console", (m) => console.log(`[console.${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => console.log(`[pageerror] ${e.message}\n${e.stack}`));
  await page.goto(`chrome-extension://${id}/app.html${process.argv[2] || "#search?q=shard"}`);
  await page.waitForTimeout(4000);
  console.log("status:", await page.textContent("#search-status").catch(() => "?"));
  console.log("results:", await page.locator("#results li").count());
  console.log("visible tab:", await page.evaluate(() => [...document.querySelectorAll(".tab")].filter((t) => !t.hidden).map((t) => t.id)));
} finally {
  await ctx.close();
  rmSync(profile, { recursive: true, force: true });
}
