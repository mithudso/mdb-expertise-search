// textsearch — the MongoDB expertise search engine, in the browser. JavaScript port of mdbx/webexport.py.
//
// Keyword ranking reproduces mdbx's SQLite FTS5 search: the unicode61 tokenizer (remove_diacritics 2,
// '_' as a token character), the porter stemmer, bm25() with column weights heading 4 / text 1 /
// source 2 (k1 1.2, b 0.75), AND first and OR as the fallback, then de-duplication. Semantic ranking
// uses the exported int8 vectors; hybrid fuses both with reciprocal-rank fusion (k = 60).
// The index files are written by `mdbx export-web`; tests/fixtures/search/golden.json pins the output.

export const K1 = 1.2;
export const B = 0.75;
export const RRF_K = 60;
export const STOPWORDS = new Set(["a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "does", "for", "from", "how",
  "i", "if", "in", "is", "it", "my", "of", "on", "or", "so", "that", "the", "this", "to", "was", "what", "when", "where",
  "which", "why", "with", "you", "your", "can", "not"]);
const TOKEN_CHAR = /[\p{L}\p{N}\p{Co}_]/u;
const WORD = /[\p{L}\p{N}_]+/gu; // Python re \w+
const PORTER_MAX = 64;
const enc = new TextEncoder();

// ---- tokenizer

function fold(tok) {
  return tok.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/** Lower-cased, diacritic-free tokens (FTS5 unicode61 with '_' as a token character), with offsets. */
export function rawTokenSpans(text) {
  const out = [];
  let cur = "";
  let start = 0;
  let i = 0;
  for (const c of text) {
    if (TOKEN_CHAR.test(c)) {
      if (!cur) start = i;
      cur += c;
    } else if (cur) {
      const t = fold(cur);
      if (t) out.push([t, start, i]);
      cur = "";
    }
    i += c.length;
  }
  if (cur) {
    const t = fold(cur);
    if (t) out.push([t, start, i]);
  }
  return out;
}

export function tokens(text) {
  return rawTokenSpans(text).map(([t]) => porter(t));
}

// ---- Porter (1980) stemmer, matching mdbx/webexport.py

const VOWELS = "aeiou";

function cons(w, i) {
  const c = w[i];
  if (VOWELS.includes(c)) return false;
  if (c === "y") return i === 0 || !cons(w, i - 1);
  return true;
}

function measure(w) {
  let n = 0, i = 0;
  const ln = w.length;
  while (i < ln && cons(w, i)) i++;
  while (i < ln) {
    while (i < ln && !cons(w, i)) i++;
    if (i >= ln) break;
    n++;
    while (i < ln && cons(w, i)) i++;
  }
  return n;
}

function hasVowel(w) {
  for (let i = 0; i < w.length; i++) if (!cons(w, i)) return true;
  return false;
}

function doubleCons(w) {
  return w.length >= 2 && w[w.length - 1] === w[w.length - 2] && cons(w, w.length - 1);
}

function cvc(w) {
  if (w.length < 3) return false;
  const n = w.length;
  return cons(w, n - 3) && !cons(w, n - 2) && cons(w, n - 1) && !"wxy".includes(w[n - 1]);
}

const STEP2 = [["ational", "ate"], ["tional", "tion"], ["enci", "ence"], ["anci", "ance"], ["izer", "ize"],
  ["bli", "ble"], ["alli", "al"], ["entli", "ent"], ["eli", "e"], ["ousli", "ous"], ["ization", "ize"],
  ["ation", "ate"], ["ator", "ate"], ["alism", "al"], ["iveness", "ive"], ["fulness", "ful"],
  ["ousness", "ous"], ["aliti", "al"], ["iviti", "ive"], ["biliti", "ble"], ["logi", "log"]];
const STEP3 = [["icate", "ic"], ["ative", ""], ["alize", "al"], ["iciti", "ic"], ["ical", "ic"], ["ful", ""],
  ["ness", ""]];
const STEP4 = ["al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement", "ment", "ent", "ion", "ou", "ism",
  "ate", "iti", "ous", "ive", "ize"];

export function porter(w) {
  const nb = enc.encode(w).length;
  if (nb < 3 || nb > PORTER_MAX) return w;
  // step 1a
  if (w.endsWith("sses")) w = w.slice(0, -2);
  else if (w.endsWith("ies")) w = w.slice(0, -2);
  else if (w.endsWith("ss")) { /* keep */ } else if (w.endsWith("s")) w = w.slice(0, -1);
  // step 1b
  let extra = false;
  if (w.endsWith("eed")) {
    if (measure(w.slice(0, -3)) > 0) w = w.slice(0, -1);
  } else {
    for (const suf of ["ed", "ing"]) {
      if (w.endsWith(suf) && hasVowel(w.slice(0, -suf.length))) {
        w = w.slice(0, -suf.length);
        extra = true;
        break;
      }
    }
  }
  if (extra) {
    if (w.endsWith("at") || w.endsWith("bl") || w.endsWith("iz")) w += "e";
    else if (doubleCons(w) && !"lsz".includes(w[w.length - 1])) w = w.slice(0, -1);
    else if (measure(w) === 1 && cvc(w)) w += "e";
  }
  // step 1c
  if (w.endsWith("y") && hasVowel(w.slice(0, -1))) w = w.slice(0, -1) + "i";
  // steps 2 and 3
  for (const table of [STEP2, STEP3]) {
    for (const [suf, rep] of table) {
      if (w.endsWith(suf)) {
        const stem = w.slice(0, w.length - suf.length);
        if (measure(stem) > 0) w = stem + rep;
        break;
      }
    }
  }
  // step 4
  for (const suf of STEP4) {
    if (w.endsWith(suf)) {
      const stem = w.slice(0, w.length - suf.length);
      if (suf === "ion") {
        if (measure(stem) > 1 && stem && "st".includes(stem[stem.length - 1])) w = stem;
      } else if (measure(stem) > 1) {
        w = stem;
      }
      break;
    }
  }
  // step 5a
  if (w.endsWith("e")) {
    const stem = w.slice(0, -1);
    const m = measure(stem);
    if (m > 1 || (m === 1 && !cvc(stem))) w = stem;
  }
  // step 5b
  if (measure(w) > 1 && doubleCons(w) && w.endsWith("l")) w = w.slice(0, -1);
  return w;
}

/** Stemmed search terms: words minus stopwords (all words if only stopwords). */
export function queryTerms(query) {
  const words = String(query).match(WORD) || [];
  const kept = words.filter((w) => !STOPWORDS.has(w.toLowerCase()));
  const use = kept.length ? kept : words;
  const out = [];
  for (const w of use) {
    const t = tokens(w);
    if (t.length) out.push(t[0]);
  }
  return out;
}

// ---- index

/**
 * The exported index. Construct with the parsed files:
 * { meta, chunks, vocab, ids: Uint32Array, wts: Uint16Array, doclen: Uint32Array, vectors: Int8Array|null }
 */
export class SearchIndex {
  constructor({ meta, chunks, vocab, ids, wts, doclen, vectors = null }) {
    this.meta = meta;
    this.paths = chunks.paths;
    this.sources = chunks.sources;
    this.kinds = chunks.kinds;
    this.rows = chunks.rows; // [pathIdx, sourceIdx, kindIdx, line, heading, text, vecIdx]
    this.vocab = vocab;
    this.ids = ids;
    this.wts = wts;
    this.doclen = doclen;
    this.n = this.rows.length;
    this.avgdl = this.n ? meta.total_tokens / this.n : 0;
    this.vectors = vectors && vectors.length ? vectors : null;
    this.dim = (meta.vectors && meta.vectors.dim) || 0;
  }

  hit(i, score, via) {
    const r = this.rows[i];
    return { id: i, path: this.paths[r[0]], source: this.sources[r[1]], kind: this.kinds[r[2]], heading: r[4],
      line: r[3], text: r[5], score, via };
  }

  allowed(i, kind, source) {
    const r = this.rows[i];
    if (kind && this.kinds[r[2]] !== kind) return false;
    return !(source && !this.sources[r[1]].toLowerCase().includes(String(source).toLowerCase()));
  }

  keywordRanked(query, kind = null, source = null) {
    const terms = queryTerms(query);
    if (!terms.length) return [];
    const uniq = [...new Set(terms)];
    for (const mode of ["AND", "OR"]) {
      const scores = new Map();
      const present = new Map();
      for (const t of uniq) {
        const v = Object.prototype.hasOwnProperty.call(this.vocab, t) ? this.vocab[t] : null;
        if (v === null) continue;
        const [df, off] = v;
        let idf = Math.log((this.n - df + 0.5) / (df + 0.5));
        if (idf <= 0) idf = 1e-6;
        const qtf = terms.filter((x) => x === t).length;
        for (let j = off; j < off + df; j++) {
          const i = this.ids[j];
          const w = this.wts[j];
          const denom = w + K1 * (1 - B + B * this.doclen[i] / this.avgdl);
          scores.set(i, (scores.get(i) ?? 0) + qtf * idf * (w * (K1 + 1)) / denom);
          present.set(i, (present.get(i) ?? 0) + 1);
        }
      }
      const need = mode === "AND" ? uniq.length : 1;
      const ranked = [];
      for (const [i, s] of scores) if (present.get(i) >= need && this.allowed(i, kind, source)) ranked.push([i, s]);
      if (ranked.length) {
        ranked.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
        return ranked;
      }
    }
    return [];
  }

  keyword(query, limit = 10, { kind = null, source = null } = {}) {
    const ranked = this.keywordRanked(query, kind, source).slice(0, limit * 3);
    return dedupe(ranked.map(([i, s]) => this.hit(i, s, "keyword")), limit);
  }

  semanticVec(qv, limit = 10, { kind = null, source = null } = {}) {
    if (!this.vectors) return [];
    const dim = this.dim;
    const ranked = [];
    for (let i = 0; i < this.n; i++) {
      const vi = this.rows[i][6];
      if (vi < 0 || !this.allowed(i, kind, source)) continue;
      const base = vi * dim;
      let s = 0;
      for (let k = 0; k < dim; k++) s += this.vectors[base + k] * qv[k];
      ranked.push([i, s / 127.0]);
    }
    ranked.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
    return dedupe(ranked.slice(0, limit * 3).map(([i, s]) => this.hit(i, s, "semantic")), limit);
  }

  hybridVec(query, qv, limit = 10, opts = {}) {
    const kw = this.keyword(query, limit * 3, opts);
    if (!qv) return kw.slice(0, limit);
    const sm = this.semanticVec(qv, limit * 3, opts);
    const fused = new Map();
    const scores = new Map();
    for (const hits of [kw, sm]) {
      hits.forEach((h, idx) => {
        scores.set(h.id, (scores.get(h.id) ?? 0) + 1.0 / (RRF_K + idx + 1));
        if (fused.has(h.id)) fused.get(h.id).via = "keyword+semantic";
        else fused.set(h.id, { ...h });
      });
    }
    const out = [...fused.values()];
    for (const h of out) h.score = scores.get(h.id);
    out.sort((a, b) => b.score - a.score || a.id - b.id);
    return dedupe(out, limit);
  }

  /** All chunks of one corpus file in line order, joined: the "show" view. */
  document(path) {
    const pi = this.paths.indexOf(path);
    if (pi < 0) return null;
    const parts = this.rows.map((r, i) => [r, i]).filter(([r]) => r[0] === pi).sort((a, b) => a[0][3] - b[0][3]);
    return { path, source: this.sources[parts[0][0][1]], kind: this.kinds[parts[0][0][2]],
      chunks: parts.map(([r, i]) => ({ id: i, line: r[3], heading: r[4], text: r[5] })) };
  }

  /** Per-source chunk counts for the facet list, largest first. */
  facets() {
    return this.meta.sources;
  }
}

export function dedupe(hits, limit) {
  const seen = new Set();
  const out = [];
  for (const h of hits) {
    const key = h.text.split(/\s+/).filter(Boolean).join(" ").slice(0, 300);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(h);
    if (out.length >= limit) break;
  }
  return out;
}

/**
 * Snippet for display: the window of `width` tokens with the most query-term hits, as segments
 * [{ text, hit }] so the caller can mark hits without building HTML. Leading/trailing "… " when cut.
 */
export function snippet(text, query, width = 24) {
  const terms = new Set(queryTerms(query));
  const spans = rawTokenSpans(text);
  if (!spans.length) return [{ text: text.slice(0, 220), hit: false }];
  const isHit = spans.map(([t]) => terms.has(porter(t)));
  let best = 0, bestCount = -1, count = 0;
  for (let i = 0; i < spans.length; i++) {
    if (isHit[i]) count++;
    if (i >= width && isHit[i - width]) count--;
    const start = Math.max(0, i - width + 1);
    if (count > bestCount) { bestCount = count; best = start; }
  }
  const end = Math.min(spans.length, best + width);
  const from = spans[best][1];
  const to = spans[end - 1][2];
  const segs = [];
  if (best > 0) segs.push({ text: "… ", hit: false });
  let pos = from;
  for (let i = best; i < end; i++) {
    const [, s, e] = spans[i];
    if (s > pos) segs.push({ text: text.slice(pos, s), hit: false });
    segs.push({ text: text.slice(s, e), hit: isHit[i] });
    pos = e;
  }
  if (to < text.length) segs.push({ text: " …", hit: false });
  return segs.map((g) => ({ ...g, text: g.text.replace(/\s+/g, " ") }));
}

// ---- semantic query embeddings via a local Ollama (optional)

export class EmbedError extends Error {}

/**
 * Embed a query with Ollama's /api/embed using the model the index was built with, L2-normalised.
 * Ollama rejects browser-extension origins with HTTP 403 unless OLLAMA_ORIGINS allows them.
 */
export async function embedQuery(query, { host = "http://127.0.0.1:11434", model = "nomic-embed-text",
  fetchImpl = fetch, timeoutMs = 8000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetchImpl(`${host.replace(/\/$/, "")}/api/embed`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, input: ["search_query: " + query] }), signal: ctrl.signal,
    });
  } catch (err) {
    throw new EmbedError(`cannot reach Ollama at ${host} (${err && err.name === "AbortError" ? "timed out" : err.message})`);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 403) {
    throw new EmbedError("Ollama refused the extension (HTTP 403). Allow it with OLLAMA_ORIGINS=chrome-extension://* and restart Ollama.");
  }
  if (!res.ok) throw new EmbedError(`Ollama /api/embed returned HTTP ${res.status}`);
  let data;
  try {
    data = await res.json();
  } catch {
    throw new EmbedError("Ollama returned a response that is not JSON");
  }
  const v = data && Array.isArray(data.embeddings) ? data.embeddings[0] : null;
  if (!Array.isArray(v) || !v.length) throw new EmbedError("Ollama returned no embedding");
  const n = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
  return v.map((x) => x / n);
}
