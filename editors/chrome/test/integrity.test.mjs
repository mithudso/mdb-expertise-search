import { test } from "node:test";
import assert from "node:assert/strict";
import { clamp, freshPending, MAX_INPUT } from "../lib/capture.js";
import { docFor } from "../lib/docs.js";
import { scanRatio, toMarkdown } from "../lib/report.js";
import { SearchIndex, embedQuery, EmbedError, tokens, queryTerms, rawTokenSpans } from "../lib/textsearch.js";
import { loadIndex } from "../lib/store.js";

test("selection cutoffs preserve Unicode and reject future handoffs", () => {
  const result = clamp("a".repeat(MAX_INPUT - 1) + "😀");
  assert.deepEqual(result, { text: "a".repeat(MAX_INPUT - 1), truncated: true });
  const exact = "a".repeat(MAX_INPUT - 2) + "😀";
  assert.deepEqual(clamp(exact), { text: exact, truncated: false });
  assert.doesNotThrow(() => encodeURIComponent(result.text));
  assert.equal(freshPending({ text: "synthetic", ts: 1001 }, 1000), false);
  assert.equal(freshPending({ text: "synthetic", ts: Infinity }, 1000), false);
});

test("unknown finding codes never inherit documentation properties", () => {
  for (const code of ["constructor", "toString", "__proto__", "unknown"]) assert.equal(docFor(code), null);
});

test("case notes contain embedded Markdown as literal content", () => {
  const code = "/*\n```\n# synthetic heading\n```\n*/\ndb.c.find({})";
  const rep = { inputQueries: 1, inputKind: "mongosh", interpreted: null, text: code, indexes: [],
    findings: [{ code: "unknown", severity: "high", pass: "P1", message: "message\n\n# synthetic heading" }],
    applied: [{ code: "rewrite", message: "rewrite\n\n# synthetic heading" }],
    evidence: [{ planSummary: "COLLSCAN`\n\n# synthetic heading" }] };
  const md = toMarkdown(rep);
  assert.match(md, /Rewritten:\n````js\n/);
  assert.equal(md.split(/^# synthetic heading$/m).length - 1, 1, "only the fenced query contains a heading line");
  assert.match(md, /\\# synthetic heading/);
});

test("scan ratios reject malformed counters", () => {
  for (const value of [NaN, Infinity, -1]) {
    assert.equal(scanRatio({ docsExamined: value, nreturned: 1 }), null);
    assert.equal(scanRatio({ docsExamined: 1, nreturned: value }), null);
  }
});

test("canonical accents retain complete UTF-16 token offsets", () => {
  const composed = "résumé", decomposed = composed.normalize("NFD");
  assert.deepEqual(tokens(decomposed), tokens(composed));
  assert.deepEqual(queryTerms(decomposed), queryTerms(composed));
  assert.deepEqual(rawTokenSpans(decomposed), [["resume", 0, decomposed.length]]);
});

function syntheticIndex() {
  return new SearchIndex({ meta: { total_tokens: 7, vectors: { dim: 2 } },
    chunks: { paths: ["synthetic.md"], sources: ["test"], kinds: ["doc"],
      rows: Array.from({ length: 7 }, (_, i) => [0, 0, 0, i + 1, "heading", i < 6 ? "duplicate" : "unique", i]) },
    vocab: { term: [7, 0] }, ids: Uint32Array.from({ length: 7 }, (_, i) => i),
    wts: new Uint16Array(7).fill(1), doclen: new Uint32Array(7).fill(1),
    vectors: Int8Array.from({ length: 14 }, (_, i) => i % 2 ? 0 : 127) });
}

test("ranking fills distinct results beyond duplicate candidates", () => {
  const idx = syntheticIndex();
  assert.deepEqual(idx.keyword("term", 2).map(h => h.text), ["duplicate", "unique"]);
  assert.deepEqual(idx.semanticVec([1, 0], 2).map(h => h.text), ["duplicate", "unique"]);
});

test("semantic ranking rejects dimension and numeric mismatches", () => {
  const idx = syntheticIndex();
  for (const qv of [[1], [1, 0, 0], [NaN, 0], ["1", 0]]) assert.throws(() => idx.semanticVec(qv), /dimension|finite|number/i);
});

test("embedding deadline covers stalled response bodies", async () => {
  let watchdog;
  try {
    const outcome = await Promise.race([
      embedQuery("synthetic", { timeoutMs: 5, fetchImpl: async (_url, { signal }) => ({ ok: true, status: 200,
        json: () => new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true })) }) })
        .then(() => "resolved", e => e),
      new Promise(resolve => { watchdog = setTimeout(() => resolve("hung"), 100); }),
    ]);
    assert.ok(outcome instanceof EmbedError, String(outcome));
    assert.match(outcome.message, /timed out/);
  } finally { clearTimeout(watchdog); }
});

test("embedding rejects malformed and zero responses and safely normalizes large values", async () => {
  const response = v => ({ fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ embeddings: [v] }) }) });
  for (const v of [["bad", 1], [null, 1], [0, 0], [Infinity, 0]]) await assert.rejects(embedQuery("synthetic", response(v)), EmbedError);
  const v = await embedQuery("synthetic", response([1e308, 1e308]));
  assert.equal(v.length, 2);
  for (const component of v) assert.ok(Math.abs(component - Math.SQRT1_2) < 1e-12);
  assert.ok(v.every(Number.isFinite));
  assert.ok(Math.abs(Math.hypot(...v) - 1) < 1e-12);
});

function files() {
  return { "meta.json": { total_tokens: 1 },
    "chunks.json": { paths: ["synthetic.md"], sources: ["test"], kinds: ["doc"], rows: [[0, 0, 0, 1, "alpha", "alpha", -1]] },
    "terms.json": { alpha: [1, 0] }, "postings.bin": new Uint8Array(4),
    "weights.bin": Uint8Array.of(1, 0), "doclen.bin": Uint8Array.of(1, 0, 0, 0) };
}

test("index loader rejects inconsistent package parts without exposing content", async () => {
  const mutations = [f => { f["weights.bin"] = new Uint8Array(); }, f => { f["doclen.bin"] = new Uint8Array(); },
    f => { f["terms.json"].alpha = [2, 0]; }, f => { f["postings.bin"][0] = 9; },
    f => { f["chunks.json"].rows[0][0] = 3; },
    f => { f["meta.json"].vectors = { count: 1, dim: 2 }; f["vectors.bin"] = Uint8Array.of(127); },
    f => { f["chunks.json"].rows[0][6] = 1; },
    f => { f["meta.json"].total_tokens = 0; f["doclen.bin"] = new Uint8Array(4); }];
  for (const mutate of mutations) {
    const f = files(); mutate(f);
    await assert.rejects(loadIndex(async name => f[name] ?? null), error => /invalid|inconsistent|missing/i.test(error.message) && !error.message.includes("alpha"));
  }
  assert.equal((await loadIndex(async name => files()[name] ?? null)).n, 1);
});

test("failed cached loads retry and concurrent retries share the load", async t => {
  const prior = globalThis.chrome;
  globalThis.chrome = { runtime: { getURL: name => name } };
  t.after(() => { globalThis.chrome = prior; });
  let attempts = 0;
  t.mock.method(globalThis, "fetch", async name => ({ ok: true, json: async () => {
    if (name === "data/meta.json" && ++attempts === 1) throw Error("synthetic read failure");
    return name.endsWith("meta.json") ? { total_tokens: 0 } : name.endsWith("chunks.json") ? { paths: [], sources: [], kinds: [], rows: [] } : {};
  }, arrayBuffer: async () => new ArrayBuffer(0) }));
  const { getIndex } = await import(`../lib/store.js?retry-regression`);
  await assert.rejects(getIndex(), /synthetic read failure/);
  const retry = getIndex();
  assert.strictEqual(retry, getIndex());
  assert.equal((await retry).n, 0);
  assert.equal(attempts, 2);
});

test("packaged transport failures remain retryable and missing optional metadata is distinct", async t => {
  const previous = globalThis.chrome; globalThis.chrome = { runtime: { getURL: name => name } };
  t.after(() => { globalThis.chrome = previous; });
  const { extensionReader } = await import("../lib/store.js");
  t.mock.method(globalThis, "fetch", async () => { throw Error("synthetic transport failure"); });
  await assert.rejects(extensionReader()("meta.json", "json"), /Could not read packaged meta\.json/);
  t.mock.method(globalThis, "fetch", async () => ({ ok: false, status: 404 }));
  assert.equal(await extensionReader()("meta.json", "json"), null);
});
