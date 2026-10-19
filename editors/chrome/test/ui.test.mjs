// Unit tests for the browser-independent parts of the extension: selection picking, the context-menu
// handoff, the Markdown case note, the docs map and the manifest.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { clamp, freshPending, MAX_INPUT, pickSelection, PENDING_TTL_MS } from "../lib/capture.js";
import { DOCS, docFor } from "../lib/docs.js";
import { optimize } from "../lib/optimize.js";
import { scanRatio, severityCounts, toMarkdown } from "../lib/report.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const FIX = join(root, "..", "..", "tests", "fixtures", "optimizer");

test("pickSelection takes the longest non-blank frame result", () => {
  assert.equal(pickSelection([{ result: "" }, { result: "db.a.find({})" }, { result: "  " }, { result: "db.b" }]), "db.a.find({})");
  assert.equal(pickSelection([]), "");
  assert.equal(pickSelection(undefined), "");
  assert.equal(pickSelection([{ result: null }, {}]), "");
});

test("clamp truncates oversized selections", () => {
  assert.deepEqual(clamp("abc"), { text: "abc", truncated: false });
  const big = clamp("x".repeat(MAX_INPUT + 5));
  assert.equal(big.text.length, MAX_INPUT);
  assert.equal(big.truncated, true);
  assert.deepEqual(clamp(undefined), { text: "", truncated: false });
});

test("freshPending accepts only recent, non-blank handoffs", () => {
  const now = 1_000_000;
  assert.equal(freshPending({ text: "db.a.find()", ts: now - 5 }, now), true);
  assert.equal(freshPending({ text: "db.a.find()", ts: now - PENDING_TTL_MS - 1 }, now), false);
  assert.equal(freshPending({ text: "   ", ts: now }, now), false);
  assert.equal(freshPending(undefined, now), false);
});

test("every finding code the optimizer can emit has a docs link", () => {
  const src = readFileSync(join(root, "lib", "optimize.js"), "utf8");
  const codes = new Set([...src.matchAll(/(?:MEDIUM|HIGH|LOW|BLOCKING|\?\s*HIGH\s*:\s*MEDIUM|acc\.key === "\$push" \? HIGH : MEDIUM), "([a-z0-9-]+)"/g)].map((m) => m[1]));
  for (const m of src.matchAll(/add\((?:HIGH|MEDIUM|LOW|docs >= 1000 \? HIGH : MEDIUM), "([a-z0-9-]+)"/g)) codes.add(m[1]);
  assert.ok(codes.size >= 30, `found only ${codes.size} codes`);
  for (const c of codes) assert.ok(docFor(c), `no docs link for ${c}`);
  for (const url of Object.values(DOCS)) assert.match(url, /^https:\/\/www\.mongodb\.com\/docs\//);
});

test("Markdown case note for a slow-query log line", () => {
  const rep = optimize(readFileSync(join(FIX, "slowlog-find.txt"), "utf8"));
  const md = toMarkdown(rep);
  assert.match(md, /^\*\*MQL optimizer \(static review\)\*\* — 1 query, 2 high, 4 medium, 1 low/);
  assert.match(md, /Input: slow-query log line, read as:\n```js\ndb\.orders\.find\(/);
  assert.match(md, /Logged evidence: plan `COLLSCAN`, 4981 ms, docsExamined 1843220, keysExamined 0, nreturned 20, scan ratio 92,161:1/);
  assert.match(md, /\*\*HIGH\*\* `log-collscan` \(P9\)/);
  assert.match(md, /\[MongoDB docs\]\(https:\/\/www\.mongodb\.com\/docs\/manual\/reference\/explain-results\/\)/);
  assert.match(md, /```js\ndb\.orders\.createIndex\(\{ customerId: 1, createdAt: -1 \}\)\n```/);
  assert.ok(md.trimEnd().endsWith("nReturned unchanged._"));
});

test("Markdown case note includes rewrites and the rewritten text", () => {
  const rep = optimize("db.c.find({ $or: [{ a: 1 }, { a: 2 }] })");
  const md = toMarkdown(rep);
  assert.match(md, /1 safe rewrite\(s\)/);
  assert.match(md, /Rewritten:\n```js\ndb\.c\.find\(\{ a: \{ \$in: \[1, 2\] \} \}\)\n```/);
  assert.deepEqual(severityCounts(rep), [["low", 0]].filter(([, n]) => n));
});

test("embedQuery: 403 explains OLLAMA_ORIGINS; success is L2-normalised", async () => {
  const { embedQuery, EmbedError } = await import("../lib/textsearch.js");
  const reply = (status, body) => async () => ({ status, ok: status < 400, json: async () => body });
  await assert.rejects(embedQuery("x", { fetchImpl: reply(403, {}) }), (e) => e instanceof EmbedError && /OLLAMA_ORIGINS/.test(e.message));
  await assert.rejects(embedQuery("x", { fetchImpl: reply(500, {}) }), /HTTP 500/);
  await assert.rejects(embedQuery("x", { fetchImpl: async () => { throw new Error("ECONNREFUSED"); } }), /cannot reach Ollama/);
  const v = await embedQuery("x", { fetchImpl: reply(200, { embeddings: [[3, 4]] }) });
  assert.deepEqual(v, [0.6, 0.8]);
});

test("scanRatio", () => {
  assert.equal(scanRatio({ docsExamined: 1000, nreturned: 0 }), "1,000:1");
  assert.equal(scanRatio({ docsExamined: 10 }), null);
});

test("manifest: MV3, minimal permissions, no host access, files exist", () => {
  const m = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8"));
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  assert.equal(m.manifest_version, 3);
  assert.equal(m.version, pkg.version, "manifest.json and package.json versions must match");
  assert.deepEqual([...m.permissions].sort(), ["activeTab", "contextMenus", "scripting", "storage"]);
  assert.equal(m.host_permissions, undefined);
  // Ollama access is optional, local-only, and requested at runtime from the About tab
  assert.deepEqual(m.optional_host_permissions, ["http://127.0.0.1/*", "http://localhost/*"]);
  assert.equal(m.omnibox.keyword, "mdb");
  assert.equal(m.content_scripts, undefined);
  assert.ok(m.description.length <= 132, "Chrome Web Store limit is 132 characters");
  for (const f of [m.action.default_popup, m.background.service_worker, ...Object.values(m.icons)]) {
    assert.ok(readFileSync(join(root, f)).length > 0, f);
  }
});

test("every runtime script parses (pages that need a DOM are not imported by the other tests)", async () => {
  const { execFileSync } = await import("node:child_process");
  const { readdirSync } = await import("node:fs");
  const scripts = ["app.js", "popup.js", "background.js", ...readdirSync(join(root, "lib")).filter((f) => f.endsWith(".js")).map((f) => `lib/${f}`)];
  for (const f of scripts) execFileSync(process.execPath, ["--check", join(root, f)], { stdio: "pipe" });
});

test("popup code never assigns HTML from page text", () => {
  for (const f of ["popup.js", "app.js", "background.js", "lib/report.js", "lib/capture.js", "lib/ui.js",
    "lib/textsearch.js", "lib/store.js"]) {
    const src = readFileSync(join(root, f), "utf8");
    assert.doesNotMatch(src, /innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(|new Function/, f);
  }
});
