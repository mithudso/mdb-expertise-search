// Debug helper: open app.html at a hash in real Chromium and print status, console messages and errors.
//   PLAYWRIGHT=/path/to/playwright/index.mjs node test/debug-app.mjs '#search?q=shard'
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { appComplete } from "./app-completion.mjs";
import { withBrowserContext } from "./browser-context.mjs";

const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const extDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
await withBrowserContext(chromium, "mql-dbg-", { headless: true, channel: "chromium",
  args: [`--disable-extensions-except=${extDir}`, `--load-extension=${extDir}`] }, async ctx => {
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker", { timeout: 15000 });
  const id = new URL(sw.url()).host;
  const page = await ctx.newPage();
  page.on("console", (m) => console.log(`[console.${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => console.log(`[pageerror] ${e.message}\n${e.stack}`));
  await page.goto(`chrome-extension://${id}/app.html${process.argv[2] || "#search?q=shard"}`);
  let complete = true;
  try {
    await page.waitForFunction(appComplete, null, { timeout: 20000 });
  } catch { complete = false; }
  console.log("completion:", complete ? "complete" : "incomplete (timeout)");
  console.log("status:", await page.textContent("#search-status").catch(() => "?"));
  console.log("results:", await page.locator("#results li").count());
  console.log("visible tab:", await page.evaluate(() => [...document.querySelectorAll(".tab")].filter((t) => !t.hidden).map((t) => t.id)));
});
