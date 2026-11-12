// Debug helper: open app.html at a hash in real Chromium and print status, console messages and errors.
//   PLAYWRIGHT=/path/to/playwright/index.mjs node test/debug-app.mjs '#search?q=shard'
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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
    await page.waitForFunction(() => {
      const [route, query] = location.hash.slice(1).split("?");
      if (route === "search" || !route) {
        if (!(new URLSearchParams(query).get("q") || "").trim()) return true;
        const status = document.getElementById("search-status");
        return /results? in \d+ ms/.test(status.textContent) || status.classList.contains("error");
      }
      if (route === "about") return Boolean(document.getElementById("stats").textContent);
      if (route === "doc") return Boolean(document.getElementById("doc").textContent);
      if (route === "recipes") return Boolean(document.getElementById("recipes").textContent);
      return Boolean(document.getElementById(`tab-${route}`) && !document.getElementById(`tab-${route}`).hidden);
    }, null, { timeout: 20000 });
  } catch { complete = false; }
  console.log("completion:", complete ? "complete" : "incomplete (timeout)");
  console.log("status:", await page.textContent("#search-status").catch(() => "?"));
  console.log("results:", await page.locator("#results li").count());
  console.log("visible tab:", await page.evaluate(() => [...document.querySelectorAll(".tab")].filter((t) => !t.hidden).map((t) => t.id)));
});
