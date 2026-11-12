// Batch runner for tests/test_web_search.py: argv[2] = exported index dir; stdin = JSON
// [{q, kind?, source?, qvec?}]; stdout = JSON [{keyword: [[id, score], ...], semantic, hybrid}].
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { loadIndex } from "../lib/store.js";

const dir = process.argv[2];
const read = async (name, kind) => {
  const p = join(dir, name);
  if (!existsSync(p)) return null;
  const buf = readFileSync(p);
  return kind === "json" ? JSON.parse(buf.toString("utf8")) : new Uint8Array(buf);
};
const idx = await loadIndex(read);
let raw = "";
process.stdin.setEncoding("utf8");
for await (const c of process.stdin) raw += c;
const pairs = (hits, position) => hits.map((h) => {
  if (!Number.isFinite(h.score)) throw new Error(`batch position ${position}: nonfinite search score`);
  return [h.id, h.score];
});
let queries;
try { queries = JSON.parse(raw); } catch { throw new Error("Invalid JSON from stdin"); }
const out = queries.map(({ q, qvec, ...opts }, position) => {
  if (qvec !== undefined && (!Array.isArray(qvec) || !qvec.every(Number.isFinite) || (idx.vectors && qvec.length !== idx.dim))) {
    throw new Error(`batch position ${position}: qvec must contain finite numbers with the index dimension`);
  }
  return {
    keyword: pairs(idx.keyword(q, 10, opts), position),
    semantic: qvec ? pairs(idx.semanticVec(qvec, 10, opts), position) : [],
    hybrid: pairs(idx.hybridVec(q, qvec ?? null, 10, opts), position),
  };
});
process.stdout.write(JSON.stringify(out));
