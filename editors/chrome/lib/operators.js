// operators — the built-in MQL operator table. JavaScript port of mdbx/mql/operators.py.
//
// The table itself is generated (scripts/gen_chrome_operators.py -> lib/operators-data.js) so there is
// one source of truth. This module adds the lookups and suggest(), a port of Python's
// difflib.get_close_matches(name, OPERATORS, n=3, cutoff=0.72) including SequenceMatcher's autojunk.

import DATA from "./operators-data.js";

export class Operator {
  constructor(name, cats, arg, doc) {
    this.name = name;
    this.cats = new Set(cats);
    this.arg = arg;
    this.doc = doc;
  }

  /** True when the operator belongs to at least one of the given categories. */
  isA(...cats) {
    return cats.some((c) => this.cats.has(c));
  }
}

/** name -> Operator, in table order (the order drives suggest() tie-breaking like Python's dict). */
export const OPERATORS = new Map(DATA.operators.map((o) => [o.name, new Operator(o.name, o.cats, o.arg, o.doc)]));
export const VARIABLES = DATA.variables;
export const FIRST_STAGE_ONLY = new Set(DATA.sets.FIRST_STAGE_ONLY);
export const LAST_STAGE_ONLY = new Set(DATA.sets.LAST_STAGE_ONLY);
export const NOT_IN_FACET = new Set(DATA.sets.NOT_IN_FACET);
export const UPDATE_PIPELINE_STAGES = new Set(DATA.sets.UPDATE_PIPELINE_STAGES);
export const STAGES = new Set(DATA.sets.STAGES);
export const UPDATE_OPS = new Set(DATA.sets.UPDATE_OPS);

export function get(name) {
  return OPERATORS.get(name) ?? null;
}

// ---- difflib port (SequenceMatcher with isjunk=None, autojunk=True) -------------------------------

/** Longest-matching-block search; mirrors SequenceMatcher.find_longest_match with no junk set. */
function findLongestMatch(a, b, b2j, alo, ahi, blo, bhi) {
  let besti = alo, bestj = blo, bestsize = 0;
  let j2len = new Map();
  for (let i = alo; i < ahi; i++) {
    const newj2len = new Map();
    for (const j of b2j.get(a[i]) ?? []) {
      if (j < blo) continue;
      if (j >= bhi) break;
      const k = (j2len.get(j - 1) ?? 0) + 1;
      newj2len.set(j, k);
      if (k > bestsize) {
        besti = i - k + 1;
        bestj = j - k + 1;
        bestsize = k;
      }
    }
    j2len = newj2len;
  }
  // Extend the match with "popular" elements that were dropped from b2j (isbjunk is always false).
  while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
    besti -= 1;
    bestj -= 1;
    bestsize += 1;
  }
  while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) {
    bestsize += 1;
  }
  return [besti, bestj, bestsize];
}

/** Return [b2j, b] where b is the code-point array of the word (seq2) and b2j its index map. */
function chainB(word) {
  const b = Array.from(word);
  const b2j = new Map();
  b.forEach((elt, i) => {
    if (!b2j.has(elt)) b2j.set(elt, []);
    b2j.get(elt).push(i);
  });
  const n = b.length;
  if (n >= 200) {
    const ntest = Math.floor(n / 100) + 1;
    for (const [elt, idx] of [...b2j]) if (idx.length > ntest) b2j.delete(elt);
  }
  return [b2j, b];
}

function matchingSize(a, b, b2j) {
  const queue = [[0, a.length, 0, b.length]];
  let total = 0;
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = findLongestMatch(a, b, b2j, alo, ahi, blo, bhi);
    if (k) {
      total += k;
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  return total;
}

function quickMatches(a, b) {
  const full = new Map();
  for (const e of b) full.set(e, (full.get(e) ?? 0) + 1);
  const avail = new Map();
  let matches = 0;
  for (const e of a) {
    const numb = avail.has(e) ? avail.get(e) : (full.get(e) ?? 0);
    avail.set(e, numb - 1);
    if (numb > 0) matches += 1;
  }
  return matches;
}

/** difflib.get_close_matches(word, possibilities, n, cutoff). */
export function getCloseMatches(word, possibilities, n = 3, cutoff = 0.72) {
  const [b2j, b] = chainB(word);
  const result = [];
  for (const x of possibilities) {
    const a = Array.from(x);
    const tot = a.length + b.length;
    const ratioOf = (m) => (tot ? (2.0 * m) / tot : 1.0);
    if (ratioOf(Math.min(a.length, b.length)) < cutoff) continue;
    if (ratioOf(quickMatches(a, b)) < cutoff) continue;
    const score = ratioOf(matchingSize(a, b, b2j));
    if (score >= cutoff) result.push([score, x]);
  }
  // heapq.nlargest(n, result): tuple order, descending (score, then string).
  result.sort((p, q) => (q[0] - p[0]) || (p[1] < q[1] ? 1 : p[1] > q[1] ? -1 : 0));
  return result.slice(0, n).map((r) => r[1]);
}

/** Closest operator names to `name` (Python suggest()). */
export function suggest(name, n = 3) {
  return getCloseMatches(name, [...OPERATORS.keys()], n, 0.72);
}
