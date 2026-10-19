// Parity: the JavaScript search engine must rank exactly like the Python reference (mdbx/webexport.py
// WebIndex, itself checked against SQLite FTS5) on the fixture index in tests/fixtures/search/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { loadIndex } from "../lib/store.js";
import { porter, queryTerms, snippet, tokens } from "../lib/textsearch.js";

const here = dirname(fileURLToPath(import.meta.url));
const FIX = join(here, "..", "..", "..", "tests", "fixtures", "search");

export function fsReader(dir) {
  return async (name, kind) => {
    const p = join(dir, name);
    if (!existsSync(p)) return null;
    const buf = readFileSync(p);
    return kind === "json" ? JSON.parse(buf.toString("utf8")) : new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
  };
}

const golden = JSON.parse(readFileSync(join(FIX, "golden.json"), "utf8"));
const idx = await loadIndex(fsReader(join(FIX, "index")));

function strip(hits) {
  return hits.map((h) => ({ id: h.id, path: h.path, line: h.line, source: h.source, kind: h.kind, via: h.via, score: h.score }));
}

function same(actual, expected, label) {
  assert.equal(actual.length, expected.length, `${label}: result count`);
  actual.forEach((a, i) => {
    const e = expected[i];
    assert.deepEqual({ ...a, score: 0 }, { ...e, score: 0 }, `${label}[${i}]`);
    assert.ok(Math.abs(a.score - e.score) <= 1e-8 * Math.max(1, Math.abs(e.score)), `${label}[${i}] score ${a.score} vs ${e.score}`);
  });
}

test("fixture index loads", () => {
  assert.ok(idx && idx.n > 10, "index has chunks");
  assert.ok(idx.vectors && idx.dim === golden.dim, "vectors present");
});

for (const r of golden.results) {
  const { q, ...opts } = r.query;
  const label = JSON.stringify(r.query);
  test(`keyword ${label}`, () => same(strip(idx.keyword(q, 10, opts)), r.keyword, "keyword"));
  test(`semantic ${label}`, () => same(strip(idx.semanticVec(r.qvec, 10, opts)), r.semantic, "semantic"));
  test(`hybrid ${label}`, () => same(strip(idx.hybridVec(q, r.qvec, 10, opts)), r.hybrid, "hybrid"));
}

test("porter stems like the reference implementation", () => {
  const cases = { caresses: "caress", ponies: "poni", cats: "cat", feed: "feed", agreed: "agre", plastered: "plaster",
    motoring: "motor", sing: "sing", conflated: "conflat", hopping: "hop", filing: "file", happy: "happi",
    relational: "relat", conditional: "condit", rational: "ration", digitizer: "digit", indexes: "index",
    sharding: "shard", queries: "queri", generalization: "gener", electrical: "electr", adjustment: "adjust",
    replacement: "replac", controll: "control", roll: "roll", hopeful: "hope", goodness: "good", "8": "8" };
  for (const [w, s] of Object.entries(cases)) assert.equal(porter(w), s, w);
});

test("tokenizer folds case and diacritics and keeps underscores", () => {
  assert.deepEqual(tokens("Café SORT_MERGE $match"), ["cafe", "sort_merg", "match"]);
  assert.deepEqual(queryTerms("why is the index slow"), ["index", "slow"]);
  assert.deepEqual(queryTerms("the and of"), ["the", "and", "of"]);
});

test("snippet marks hits without HTML", () => {
  const segs = snippet("Compound indexes order keys by Equality, then Sort, then Range.", "compound sort");
  assert.ok(segs.some((s) => s.hit && /compound/i.test(s.text)));
  assert.ok(segs.some((s) => s.hit && /sort/i.test(s.text)));
  assert.equal(segs.map((s) => s.text).join("").includes("<"), false);
});

test("document() rebuilds a file from its chunks in line order", () => {
  const d = idx.document("skills/mongodb-expert/references/sharding.md");
  assert.ok(d && d.chunks.length >= 2);
  assert.deepEqual(d.chunks.map((c) => c.line), [...d.chunks.map((c) => c.line)].sort((a, b) => a - b));
  assert.equal(idx.document("nope.md"), null);
});
