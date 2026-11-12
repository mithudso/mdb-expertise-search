// Lifecycle shared by opt-in browser scripts, also exercised with a synthetic Chromium API.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, parse } from "node:path";

export async function withBrowserContext(chromium, prefix, launchOptions, work) {
  const profile = mkdtempSync(join(tmpdir(), prefix));
  let context, primary;
  try {
    context = await chromium.launchPersistentContext(profile, launchOptions);
    return await work(context);
  } catch (error) {
    primary = error;
    throw error;
  } finally {
    let cleanup;
    try { await context?.close(); } catch (error) { cleanup = error; }
    try { rmSync(profile, { recursive: true, force: true }); } catch (error) { cleanup ??= error; }
    if (!primary && cleanup) throw cleanup;
  }
}

export function screenshotPaths(path) {
  const { dir, name, ext } = parse(path);
  return { popup: path, app: join(dir, `${name}-app${ext || ".png"}`), search: join(dir, `${name}-popup-search${ext || ".png"}`) };
}
