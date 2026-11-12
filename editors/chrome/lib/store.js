// store — load the packaged search index (data/*, written by `mdbx export-web`).
import { SearchIndex } from "./textsearch.js";

/**
 * Load the index through `read(name, kind)` where kind is "json" or "bytes" and a missing optional file
 * resolves to null. Returns a SearchIndex, or null when the extension was packaged without data.
 */
export async function loadIndex(read) {
  const safeRead = async (name, kind) => {
    try { return await read(name, kind); }
    catch (error) {
      if (error instanceof SyntaxError) throw new Error(`Invalid packaged ${name}`);
      throw error;
    }
  };
  const meta = await safeRead("meta.json", "json");
  if (meta === null) return null;
  const [chunks, vocab, ids, wts, doclen, vectors] = await Promise.all([
    safeRead("chunks.json", "json"), safeRead("terms.json", "json"), safeRead("postings.bin", "bytes"),
    safeRead("weights.bin", "bytes"), safeRead("doclen.bin", "bytes"), meta.vectors ? safeRead("vectors.bin", "bytes") : null,
  ]);
  const invalid = name => { throw new Error(`Invalid or inconsistent packaged ${name}`); };
  const whole = n => Number.isSafeInteger(n) && n >= 0;
  if (!meta || typeof meta !== "object" || !Number.isFinite(meta.total_tokens) || meta.total_tokens < 0) invalid("meta.json");
  if (meta.sources !== undefined && (!Array.isArray(meta.sources) || !meta.sources.every(s => s && typeof s === "object" && typeof s.source === "string" && typeof s.kind === "string" && whole(s.chunks)))) invalid("meta.json");
  if (meta.recipes !== undefined && (!Array.isArray(meta.recipes) || !meta.recipes.every(r => r && typeof r === "object" && ["name", "title", "summary"].every(k => typeof r[k] === "string") && (r.path === null || typeof r.path === "string") && (r.applies_to === undefined || (Array.isArray(r.applies_to) && r.applies_to.every(v => typeof v === "string")))))) invalid("meta.json");
  if (meta.by_kind !== undefined && (!meta.by_kind || typeof meta.by_kind !== "object" || Array.isArray(meta.by_kind) || !Object.values(meta.by_kind).every(whole))) invalid("meta.json");
  for (const k of ["chunks", "files", "terms", "postings"]) if (meta[k] !== undefined && !whole(meta[k])) invalid("meta.json");
  if (!chunks || !["paths", "sources", "kinds", "rows"].every(k => Array.isArray(chunks[k]))) invalid("chunks.json");
  for (const field of ["paths", "sources", "kinds"]) if (!chunks[field].every(x => typeof x === "string")) invalid("chunks.json");
  if (!vocab || typeof vocab !== "object" || Array.isArray(vocab)) invalid("terms.json");
  const own = (u8, size, name) => {
    if (!(u8 instanceof Uint8Array) || u8.byteLength % size) invalid(name);
    return u8.slice().buffer;
  };
  const postings = new Uint32Array(own(ids, 4, "postings.bin"));
  const weights = new Uint16Array(own(wts, 2, "weights.bin"));
  const lengths = new Uint32Array(own(doclen, 4, "doclen.bin"));
  if (weights.length !== postings.length) invalid("weights.bin");
  if (lengths.length !== chunks.rows.length || lengths.reduce((sum, n) => sum + n, 0) !== meta.total_tokens) invalid("doclen.bin");
  if (meta.chunks !== undefined && meta.chunks !== chunks.rows.length) invalid("meta.json");
  if (meta.postings !== undefined && meta.postings !== postings.length) invalid("meta.json");
  if (meta.terms !== undefined && meta.terms !== Object.keys(vocab).length) invalid("meta.json");
  if (postings.length && !meta.total_tokens) invalid("doclen.bin");
  if (postings.some(n => n >= chunks.rows.length)) invalid("postings.bin");
  if (weights.some(n => !n)) invalid("weights.bin");
  const ranges = Object.values(vocab);
  if (!ranges.every(v => Array.isArray(v) && v.length === 2 && v.every(whole) && v[0] > 0 && v[0] <= chunks.rows.length && v[1] + v[0] <= postings.length)) invalid("terms.json");
  ranges.sort((a, b) => a[1] - b[1]);
  let end = 0;
  for (const [count, offset] of ranges) {
    if (offset !== end) invalid("terms.json");
    for (let i = offset + 1; i < offset + count; i++) if (postings[i] <= postings[i - 1]) invalid("postings.bin");
    end += count;
  }
  if (end !== postings.length) invalid("terms.json");
  let vectorData = null, vectorCount = 0;
  if (meta.vectors) {
    const { dim, count } = meta.vectors;
    if (!whole(dim) || !dim || !whole(count) || !count) invalid("meta.json");
    vectorData = new Int8Array(own(vectors, 1, "vectors.bin"));
    if (vectorData.length !== dim * count) invalid("vectors.bin");
    vectorCount = count;
  }
  for (const r of chunks.rows) {
    if (!Array.isArray(r) || r.length !== 7 || ![0, 1, 2].every((i) => whole(r[i]) && r[i] < chunks[["paths", "sources", "kinds"][i]].length) ||
      !whole(r[3]) || r[3] < 1 || typeof r[4] !== "string" || typeof r[5] !== "string" ||
      !Number.isSafeInteger(r[6]) || r[6] < -1 || (r[6] !== -1 && r[6] >= vectorCount)) invalid("chunks.json");
  }
  const completeMeta = { sources: [], recipes: [], by_kind: {}, files: chunks.paths.length, chunks: chunks.rows.length, terms: Object.keys(vocab).length, postings: postings.length, ...meta };
  completeMeta.recipes = completeMeta.recipes.filter(r => r.path !== null);
  return new SearchIndex({ meta: completeMeta, chunks, vocab, ids: postings, wts: weights, doclen: lengths, vectors: vectorData });
}

/** Reader for extension pages: fetches files packaged under data/. */
export function extensionReader(base = "data/") {
  return async (name, kind) => {
    let res;
    try {
      res = await fetch(chrome.runtime.getURL(base + name));
    } catch {
      throw new Error(`Could not read packaged ${name}`);
    }
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(`Could not read packaged ${name}`);
    }
    return kind === "json" ? res.json() : new Uint8Array(await res.arrayBuffer());
  };
}

let cached = null;

/** The extension's index, loaded once per page. */
export function getIndex() {
  if (globalThis.chrome?.runtime?.getManifest?.().mdbx_data === false) return Promise.resolve(null);
  if (!cached) {
    cached = loadIndex(extensionReader()).catch(error => { cached = null; throw error; });
  }
  return cached;
}
