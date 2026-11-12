// Enumerate only the unit suites; do not include opt-in browser scripts or batch helpers.
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
const here = dirname(fileURLToPath(import.meta.url));
const files = readdirSync(here).filter(name => name.endsWith(".test.mjs")).sort().map(name => join(here, name));
if (!files.length) throw new Error("No unit test suites found");
const result = spawnSync(process.execPath, ["--test", ...files], { stdio: "inherit" });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
