// optimize — static MQL query optimizer. JavaScript port of mdbx/mql/optimize.py.
//
// Finds every db.<coll>.find/aggregate/count/update/delete/watch call, runs the audit passes that need
// no cluster connection (P2 index use & ESR, P4 operator anti-patterns, P5 stage order, P6 sort and
// cursor cost, P7 projection, P8 pagination, plus P9 evidence from log lines), recommends ESR-ordered
// indexes and applies result-preserving rewrites until nothing changes (cap 3).
//
// The Python module is the reference. tests/fixtures/optimizer/*.golden.json pins its output and
// editors/chrome/test/parity.test.mjs checks this port against every golden file.

import { parse } from "./parser.js";
import { normalize } from "./normalize.js";

export const BLOCKING = "blocking", HIGH = "high", MEDIUM = "medium", LOW = "low";
export const SEVERITY_ORDER = { blocking: 0, high: 1, medium: 2, low: 3 };

const REF = "skills/mongodb-expert/references/";
export const REFS = {
  shape: REF + "mongodb-query-shape-optimization.md",
  index: REF + "mongodb-compound-index-design.md",
  special: REF + "mongodb-special-indexes-and-index-builds.md",
  explain: REF + "mongodb-explain-plans-and-query-planner.md",
  planner: REF + "mongodb-advanced-explain-and-planner-changes.md",
  agg: REF + "mongodb-aggregation-pipeline.md",
  perf: REF + "mongodb-query-performance.md",
  optimizer: REF + "deep-mongodb-mql-query-optimizer.md",
};

const TARGET_METHODS = {
  find: 0, findOne: 0, countDocuments: 0, count: 0, distinct: 1,
  deleteOne: 0, deleteMany: 0, remove: 0, findOneAndDelete: 0,
  findOneAndUpdate: 0, updateOne: 0, updateMany: 0, update: 0,
  findOneAndReplace: 0, replaceOne: 0,
  aggregate: null, watch: null,
};
const RANGE_OPS = new Set(["$gt", "$gte", "$lt", "$lte"]);
const NEG_OPS = new Set(["$ne", "$nin", "$not"]);
const EQ_KINDS = new Set(["string", "number", "bool", "null", "call", "ident", "member", "array", "undefined"]);
const TRANSPARENT = new Set(["$sort", "$project", "$addFields", "$set", "$unset", "$lookup", "$unwind"]);
const KV_PAIRS = [["k", "v"], ["key", "value"], ["name", "value"], ["type", "value"], ["n", "v"]];
const NUMERIC_STR = /^[-+]?\d+(\.\d+)?$/;
const IN_SORT_LIMIT = 201;
const IDENT_FULL = /^[A-Za-z_$][\w$]*$/;

const has = Object.prototype.hasOwnProperty;

/** Python repr(str) with single quotes swapped for double quotes (index key rendering). */
function pyReprDq(k) {
  const q = k.includes("'") && !k.includes('"') ? '"' : "'";
  let body = k.replace(/\\/g, "\\\\");
  if (q === "'") body = body.replace(/'/g, "\\'");
  return (q + body + q).replace(/'/g, '"');
}

function keyText(k) {
  return IDENT_FULL.test(k) ? k : pyReprDq(k);
}

/** Python-compatible number formatting: integers without a decimal point. */
export function fmt(x) {
  return Number.isInteger(x) ? String(x) : String(x);
}

/** Python round(): round half to even. */
function pyRound(x) {
  const f = Math.floor(x);
  const diff = x - f;
  if (diff > 0.5) return f + 1;
  if (diff < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

export class IndexRec {
  constructor(collection, keys, rationale) {
    this.collection = collection;
    this.keys = keys; // [[field, dir], ...]
    this.rationale = rationale;
  }

  shell() {
    const body = this.keys.map(([k, d]) => `${keyText(k)}: ${d}`).join(", ");
    return `db.${this.collection}.createIndex({ ${body} })`;
  }
}

function num(n) {
  if (!n || n.kind !== "number") return null;
  const v = Number(n.value);
  return Number.isNaN(v) && n.value !== "NaN" && typeof n.value === "string" ? null : v;
}

function startsWithAnchor(s) {
  return s.startsWith("^") || s.startsWith("\\A");
}

function splitRegex(value) {
  const s = String(value);
  const i = s.lastIndexOf("/");
  return [s.slice(0, i), s.slice(i + 1)];
}

function isEqValue(v) {
  if (EQ_KINDS.has(v.kind)) return true;
  return v.kind === "object" && !v.props.some((p) => p.key.startsWith("$"));
}

function uniq(items) {
  const out = [];
  for (const i of items) if (!out.includes(i)) out.push(i);
  return out;
}

function projectionFields(proj) {
  if (!proj || proj.kind !== "object") return [];
  const out = [];
  for (const p of proj.props) {
    if (p.key === "_id") continue;
    if (num(p.value) === 1 || (p.value !== null && p.value.kind === "bool" && p.value.value)) out.push(p.key);
    else return [];
  }
  return out;
}

function matchFields(v) {
  const out = new Set();
  for (const p of v.props) {
    if (["$expr", "$where", "$text", "$jsonSchema"].includes(p.key)) return null;
    if (["$and", "$or", "$nor"].includes(p.key) && p.value !== null && p.value.kind === "array") {
      for (const it of p.value.items) {
        if (it.kind !== "object") return null;
        const sub = matchFields(it);
        if (sub === null) return null;
        for (const x of sub) out.add(x);
      }
    } else if (!p.key.startsWith("$")) {
      out.add(p.key.split(".")[0]);
    }
  }
  return out;
}

function produced([name, v]) {
  if (v === null) return new Set(["*"]);
  if ((name === "$addFields" || name === "$set") && v.kind === "object") return new Set(v.props.map((p) => p.key.split(".")[0]));
  if (name === "$project" && v.kind === "object") {
    const out = new Set();
    for (const p of v.props) {
      const pv = p.value;
      if (pv === null || !(pv.kind === "number" || pv.kind === "bool")) out.add(p.key.split(".")[0]);
    }
    return out;
  }
  if (name === "$lookup" && v.kind === "object") {
    const out = new Set(v.props.filter((p) => p.key === "as" && p.value !== null && p.value.kind === "string")
      .map((p) => String(p.value.value).split(".")[0]));
    return out.size ? out : new Set(["*"]);
  }
  if (name === "$unwind") {
    let path = null;
    if (v.kind === "string") path = v.value;
    else {
      const pp = v.props.find((p) => p.key === "path" && p.value !== null);
      path = pp ? pp.value.value : null;
    }
    const extra = (v.kind === "object" ? v.props : []).filter((p) => p.key === "includeArrayIndex" && p.value !== null)
      .map((p) => String(p.value.value));
    const out = new Set(path ? [String(path).replace(/^\$+/, "").split(".")[0]] : ["*"]);
    for (const e of extra) out.add(e);
    return out;
  }
  if (name === "$unset") {
    const names = v.kind === "string" ? [v] : v.kind === "array" ? v.items : [];
    return new Set(names.filter((n) => n.kind === "string").map((n) => String(n.value).split(".")[0]));
  }
  return new Set();
}

function slices([, v], fieldname) {
  if (v === null) return false;
  for (const n of v.walk()) {
    if (n.kind !== "object") continue;
    for (const p of n.props) {
      if (p.key === "$slice" && p.value !== null && p.value.kind === "array" && p.value.items.length) {
        const a = p.value.items[0];
        if (a.kind === "string" && String(a.value) === "$" + fieldname) return true;
      }
    }
  }
  return false;
}

function intersects(a, b) {
  for (const x of a) if (b.has(x)) return true;
  return false;
}

class Audit {
  constructor(text) {
    this.text = text;
    [this.statements] = parse(text);
    this.vars = new Map();
    for (const s of this.statements) if (s.decl) this.vars.set(s.decl, s.node);
    this.findings = [];
    this.indexes = [];
    this.targets = [];
    this.seenPipelines = new Set();
  }

  src(n) {
    return this.text.slice(n.start, n.end);
  }

  add(span, sev, code, pid, msg, { fix = null, ref = "shape" } = {}) {
    let s, e;
    if (Array.isArray(span)) [s, e] = span;
    else if (has.call(span, "keyStart")) [s, e] = [span.keyStart, span.keyEnd];
    else [s, e] = [span.start, span.end];
    this.findings.push({ start: s, end: Math.max(e, s + 1), severity: sev, code, pass: pid, message: msg, fix,
      ref: has.call(REFS, ref) ? REFS[ref] : ref });
  }

  resolve(n) {
    if (n && n.kind === "ident" && this.vars.has(String(n.value))) return this.vars.get(String(n.value));
    return n;
  }

  run() {
    for (const st of this.statements) this.statement(st);
  }

  statement(st) {
    const tops = st.node.walk().filter((c) => c.kind === "call");
    const inner = new Set();
    for (const c of tops) {
      let t = c.target;
      while (t !== null && (t.kind === "member" || t.kind === "call")) {
        if (t.kind === "call") inner.add(t);
        t = t.target;
      }
    }
    for (const c of tops) if (!inner.has(c)) this.chain(c);
  }

  chain(call) {
    let calls = [];
    let n = call;
    while (n !== null && n.kind === "call" && n.target !== null && n.target.kind === "member") {
      calls.push([String(n.target.value), n]);
      n = n.target.target;
    }
    calls.reverse();
    let coll = null;
    if (n !== null && n.kind === "member" && n.target !== null && n.target.kind === "ident" && n.target.value === "db") {
      coll = String(n.value);
    }
    if (calls.length && calls[0][0] === "getCollection" && n !== null && n.kind === "ident" && n.value === "db") {
      const args = calls[0][1].items;
      coll = args.length && args[0].kind === "string" ? String(args[0].value) : "collection";
      calls = calls.slice(1);
    }
    if (coll === null || !calls.length || !has.call(TARGET_METHODS, calls[0][0])) return;
    const [method, base] = calls[0];
    const chain = new Map();
    for (const [name, c] of calls.slice(1)) chain.set(name, c);
    const t = { kind: Audit.kindOf(method), collection: coll, method, start: call.start, end: call.end,
      filter: null, projection: null, sort: null, pipeline: null, chain };
    const argi = TARGET_METHODS[method];
    if (argi === null) {
      t.pipeline = base.items.length ? this.resolve(base.items[0]) : null;
    } else {
      if (base.items.length > argi) t.filter = this.resolve(base.items[argi]);
      if ((method === "find" || method === "findOne") && base.items.length > 1) t.projection = this.resolve(base.items[1]);
      if (method === "findOneAndUpdate" && base.items.length > 2) {
        const opts = base.items[2];
        for (const p of opts.kind === "object" ? opts.props : []) {
          if (p.key === "sort") t.sort = p.value;
          if (p.key === "projection") t.projection = p.value;
        }
      }
    }
    if (chain.has("sort") && chain.get("sort").items.length) t.sort = this.resolve(chain.get("sort").items[0]);
    if (chain.has("projection") && chain.get("projection").items.length) t.projection = this.resolve(chain.get("projection").items[0]);
    this.targets.push(t);
    this.auditTarget(t, base);
  }

  static kindOf(method) {
    if (method === "find" || method === "findOne") return "find";
    if (method === "count" || method === "countDocuments") return "count";
    return { aggregate: "aggregate", watch: "watch", distinct: "distinct" }[method] ?? "write";
  }

  auditTarget(t, base) {
    let preds = [];
    const hasSort = t.sort !== null && t.sort.kind === "object" && t.sort.props.length > 0;
    if (t.filter !== null && t.filter.kind === "object") preds = this.filter(t.filter, { hasSort });
    if (t.pipeline !== null && t.pipeline.kind === "array") {
      if (this.seenPipelines.has(t.pipeline)) return;
      this.seenPipelines.add(t.pipeline);
      this.pipeline(t, t.pipeline);
      return;
    }
    this.cursor(t, base);
    if (["find", "count", "distinct", "write"].includes(t.kind)) this.recommend(t, preds, t.sort, t.projection);
  }

  cursor(t, base) {
    const ch = t.chain;
    const skip = ch.get("skip");
    const n = skip && skip.items.length ? num(skip.items[0]) : null;
    if (n !== null && n >= 1000) {
      this.add(skip, MEDIUM, "deep-skip", "P8",
        `skip(${Math.trunc(n)}) walks and discards ${Math.trunc(n)} index keys or documents on every page, and on ` +
        "a sharded collection mongos asks each shard for limit+skip. Use keyset pagination: " +
        "sort on a unique key and filter { _id: { $gt: lastSeenId } } with limit().", { ref: "perf" });
    }
    if (t.sort !== null && !ch.has("limit") && t.kind === "find" && t.method === "find") {
      this.add(ch.get("sort") ?? base, LOW, "sort-no-limit", "P6",
        "sort() without limit(): if no index supplies this order, the whole result is sorted in " +
        "memory (100 MB blocking-sort cap; spills or fails). Back the sort with an index or add a limit.", { ref: "perf" });
    }
    if (ch.has("hint")) {
      this.add(ch.get("hint"), LOW, "pinned-hint", "P2",
        "hint() pins a plan in application code. Compare explain() with and without it; on 8.0+ " +
        "prefer setQuerySettings (persistent, per query shape) for an intentional pin.", { ref: "planner" });
    }
    const bs = ch.get("batchSize");
    const b = bs && bs.items.length ? num(bs.items[0]) : null;
    if (b !== null && b < 20) {
      this.add(bs, MEDIUM, "tiny-batch", "P6",
        `batchSize(${Math.trunc(b)}) multiplies getMore round-trips; on a change stream each getMore re-scans ` +
        "the oplog window. Use the default (101 first batch, then up to 16 MiB) or a larger value.", { ref: "perf" });
    }
    if (t.method === "count") {
      this.add(base.target, LOW, "legacy-count", "P6",
        "count() is deprecated and can be inaccurate on sharded clusters: use countDocuments(filter), " +
        "or estimatedDocumentCount() for an unfiltered total (reads metadata only).", { ref: "perf" });
    }
    if (t.method === "countDocuments" && (t.filter === null || (t.filter.kind === "object" && !t.filter.props.length))) {
      this.add(base, MEDIUM, "count-all", "P6",
        "countDocuments({}) scans the collection or the _id index. For a whole-collection total use " +
        "estimatedDocumentCount(), which reads collection metadata.",
        { fix: base.end === t.end ? `db.${t.collection}.estimatedDocumentCount()` : null, ref: "perf" });
    }
    if (t.method === "distinct") {
      this.add(base.target, LOW, "distinct-16mb", "P6",
        "distinct() returns one document capped at 16 MB and can use DISTINCT_SCAN only with an index " +
        "led by the field. For large or sharded results use $group.", { ref: "perf" });
    }
  }

  filter(obj, { hasSort, prefix = "", rooted = true }) {
    let preds = [];
    const dotted = new Map();
    for (const p of obj.props) {
      const v = p.value;
      if (v === null) continue;
      if (p.key === "$and" && v.kind === "array") {
        for (const it of v.items) if (it.kind === "object") preds = preds.concat(this.filter(it, { hasSort, prefix, rooted }));
      } else if ((p.key === "$or" || p.key === "$nor") && v.kind === "array") {
        for (const it of v.items) if (it.kind === "object") this.filter(it, { hasSort, prefix, rooted: false });
        if (p.key === "$or") this.orRules(obj, p, { hasSort, rooted });
      } else if (p.key === "$where") {
        this.add(p, HIGH, "where", "P4",
          "$where runs JavaScript per document, cannot use an index, and is deprecated from 8.0. " +
          "Rewrite with native query operators or $expr.");
      } else if (p.key === "$expr") {
        this.exprRule(p);
      } else if (p.key === "$text" || p.key.startsWith("$")) {
        continue;
      } else {
        const name = prefix + p.key;
        if (p.key.includes(".")) {
          const i = p.key.lastIndexOf(".");
          const head = p.key.slice(0, i), tail = p.key.slice(i + 1);
          if (!dotted.has(head)) dotted.set(head, new Set());
          dotted.get(head).add(tail);
        }
        preds = preds.concat(this.field(p, name, { hasSort }));
      }
    }
    for (const [head, subs] of dotted) {
      const pair = KV_PAIRS.find((pr) => pr.every((x) => subs.has(x)));
      if (pair) {
        const [k, v] = pair;
        const span = obj.props.find((p) => p.key.startsWith(head + "."));
        this.add(span, BLOCKING, "kv-without-elemmatch", "P4",
          `Separate predicates on ${head}.${k} and ${head}.${v} can be satisfied by different elements of ` +
          `the ${head} array, so an element ${k}=a,${v}=1 next to ${k}=b,${v}=2 matches ${k}=a,${v}=2. Put ` +
          `both inside { ${head}: { $elemMatch: { ${k}: …, ${v}: … } } } and index ` +
          `{ "${head}.${k}": 1, "${head}.${v}": 1 }. Reported, not applied: it changes the result set.`);
      }
    }
    return preds;
  }

  field(p, name, { hasSort }) {
    const v = p.value;
    if (v.kind === "regex") {
      const [pat, flags] = splitRegex(v.value);
      this.regexRule(v, pat, flags);
      return [{ field: name, kind: startsWithAnchor(String(v.value)) && !flags.includes("i") ? "regex" : "other", nIn: 0 }];
    }
    if (v.kind !== "object" || !v.props.length || !v.props.every((q) => q.key.startsWith("$"))) {
      return [{ field: name, kind: "eq", nIn: 0 }];
    }
    const keys = new Map();
    for (const q of v.props) keys.set(q.key, q);
    const out = [];
    const lo = keys.get("$gte"), hi = keys.get("$lte");
    if (lo && hi && lo.value !== null && hi.value !== null && this.src(lo.value).trim() === this.src(hi.value).trim()) {
      const only = v.props.length === 2;
      this.add(v, MEDIUM, "degenerate-range", "P4",
        `${name}: $gte and $lte carry the same value, which is an equality the planner treats as a ` +
        "range (breaks ESR key order and invites near-tied plans). Rewrite to an equality.",
        { fix: only ? this.src(lo.value) : null });
      return [{ field: name, kind: "eq", nIn: 0 }];
    }
    for (const [op, q] of keys) {
      const qv = q.value;
      if (op === "$eq") {
        out.push({ field: name, kind: "eq", nIn: 0 });
      } else if (op === "$in" && qv !== null && qv.kind === "array") {
        const n = qv.items.length;
        out.push({ field: name, kind: n < IN_SORT_LIMIT ? "in" : "range", nIn: n });
        if (n >= 10000) {
          this.add(q, HIGH, "huge-in", "P4",
            `$in with ${n} values: parse, plan and bounds cost grow with every value. Load the set ` +
            "into a collection and $lookup, or batch the query.");
        } else if (n >= 1000) {
          this.add(q, MEDIUM, "large-in", "P4", `$in with ${n} values: consider batching or a join collection.`);
        } else if (n >= IN_SORT_LIMIT && hasSort) {
          this.add(q, MEDIUM, "in-blocks-sort", "P4",
            `$in with ${n} values (>= ${IN_SORT_LIMIT}) is planned like a range, so a following sort ` +
            "cannot use SORT_MERGE over the index and becomes a blocking sort. Split the list or " +
            "keep it under 201 values.");
        }
      } else if (RANGE_OPS.has(op)) {
        if (qv !== null && qv.kind === "string" && NUMERIC_STR.test(String(qv.value))) {
          this.add(qv, BLOCKING, "string-numeric-compare", "P4",
            `${name} ${op} "${qv.value}" compares strings lexicographically ("10" < "2"). If ` +
            "the field holds numbers as strings, results are wrong; store numbers as numbers. " +
            "Reported, not applied.");
        }
        out.push({ field: name, kind: "range", nIn: 0 });
      } else if (NEG_OPS.has(op) || (op === "$exists" && qv !== null && qv.kind === "bool" && !qv.value)) {
        this.add(q, MEDIUM, "negation", "P4",
          `${name}: ${op}${op !== "$exists" ? "" : ": false"} cannot use selective index bounds and ` +
          "also matches documents missing the field. Where the domain is known, match the wanted " +
          "values positively ($in / equality) — this changes results unless the field is always " +
          "present, so it is not auto-applied.");
        out.push({ field: name, kind: "neg", nIn: 0 });
      } else if (op === "$exists") {
        out.push({ field: name, kind: "exists", nIn: 0 });
      } else if (op === "$regex") {
        const opts = keys.get("$options");
        let flags = opts && opts.value !== null && opts.value.kind === "string" ? String(opts.value.value) : "";
        let pat = qv !== null && (qv.kind === "string" || qv.kind === "regex") ? String(qv.value) : "";
        if (qv !== null && qv.kind === "regex") {
          const [p2, f2] = splitRegex(pat);
          pat = p2;
          flags += f2;
        }
        if (qv !== null) this.regexRule(qv, pat, flags);
        out.push({ field: name, kind: startsWithAnchor(pat) && !flags.includes("i") ? "regex" : "other", nIn: 0 });
      } else if (op === "$elemMatch") {
        out.push({ field: name, kind: "other", nIn: 0 });
      }
    }
    return out.length ? out : [{ field: name, kind: "other", nIn: 0 }];
  }

  regexRule(node, pat, flags) {
    if (!startsWithAnchor(pat)) {
      this.add(node, MEDIUM, "unanchored-regex", "P4",
        `/${pat}/ is not anchored, so it scans every index key (or document). Anchor it with ^ if ` +
        "the value is a prefix, or use Atlas Search for substring / full-text matching.");
    } else if (flags.includes("i")) {
      this.add(node, MEDIUM, "case-insensitive-regex", "P4",
        `/${pat}/${flags}: a case-insensitive regex cannot use tight index bounds even when anchored. ` +
        "Store a normalized lower-case copy, or query with a strength-2 collation that matches an " +
        "index built with the same collation.", { ref: "index" });
    }
  }

  orRules(parent, p, { hasSort, rooted }) {
    const v = p.value;
    const branches = v.items.filter((it) => it.kind === "object");
    const fields = new Set(branches.filter((b) => b.props.length === 1).map((b) => b.props[0].key));
    const simple = branches.every((b) => b.props.length === 1 && !b.props[0].key.startsWith("$") &&
      b.props[0].value !== null && isEqValue(b.props[0].value));
    if (branches.length >= 2 && simple && fields.size === 1) {
      const f = [...fields][0];
      const vals = branches.map((b) => this.src(b.props[0].value)).join(", ");
      const clash = parent.props.some((q) => q.key === f);
      this.add([p.start, p.end], MEDIUM, "or-to-in", "P4",
        `$or of equalities on one field (${f}) is an $in: one index scan with point bounds instead ` +
        "of a subplan per branch, and sort-compatible.",
        { fix: clash ? null : `${keyText(f)}: { $in: [${vals}] }` });
      return;
    }
    if (rooted && hasSort) {
      this.add(p, MEDIUM, "rooted-or-sort", "P4",
        "A top-level $or combined with a sort can pick a blocking SORT instead of merging sorted " +
        "branch scans (SERVER-19114). Prefer $in where the branches share a field, or give each " +
        "branch an index whose order matches the sort.");
    }
    if (branches.length >= 2) {
      this.add(p, LOW, "or-branch-indexes", "P2",
        "The planner uses indexes for an $or only when EVERY branch has a usable index; one unindexed " +
        "branch turns the whole query into a collection scan. See the per-branch index " +
        "recommendations.", { ref: "index" });
    }
  }

  exprRule(p) {
    const v = p.value;
    if (v === null || v.kind !== "object" || v.props.length !== 1) return;
    const op = v.props[0].key;
    const args = v.props[0].value;
    const simple = ["$eq", "$lt", "$lte", "$gt", "$gte"].includes(op) && args !== null && args.kind === "array" &&
      args.items.length === 2 && args.items.filter((a) => a.kind === "string" && String(a.value).startsWith("$") &&
        !String(a.value).startsWith("$$")).length === 1;
    if (!simple) {
      this.add(p, MEDIUM, "expr-unindexable", "P4",
        `$expr with ${op} is evaluated per document and cannot use index bounds (only a plain ` +
        "$eq/$lt/$lte/$gt/$gte of one field against a constant can). Rewrite with query operators " +
        "where equivalent, or precompute the value into a field at write time.");
    }
  }

  pipeline(t, arr) {
    const stages = arr.items.filter((it) => it.kind === "object" && it.props.length === 1)
      .map((it) => [it.props[0].key, it.props[0].value, it]);
    const names = stages.map((s) => s[0]);
    if (!stages.length) return;
    if (t.kind === "watch" && names[0] !== "$match") {
      this.add(stages[0][2], MEDIUM, "changestream-match-first", "P5",
        "Put the event-narrowing $match (operationType, ns, fields) first so it is pushed into the " +
        "oplog scan; otherwise every event flows through the later stages.", { ref: "agg" });
    }
    this.hoistMatch(arr, stages);
    stages.forEach(([name, v, item], i) => {
      if (v === null) return;
      if (name === "$match" && v.kind === "object") {
        const afterSort = i + 1 < stages.length && stages[i + 1][0] === "$sort";
        this.filter(v, { hasSort: afterSort });
      } else if (name === "$sample" && i > 0) {
        this.add(item, MEDIUM, "sample-not-first", "P5",
          "$sample uses a random cursor only as the first stage; later it reads and sorts the " +
          "whole input randomly.", { ref: "agg" });
      } else if (name === "$skip") {
        const n = num(v);
        if (n !== null && n >= 1000) {
          this.add(item, MEDIUM, "deep-skip", "P8",
            `$skip ${Math.trunc(n)} still produces and discards ${Math.trunc(n)} documents per page; use keyset ` +
            "pagination ($match on the last seen sort key).", { ref: "perf" });
        }
      } else if (name === "$sort") {
        const nxt = i + 1 < names.length ? names[i + 1] : null;
        if (i > 0 && names[i - 1] === "$search") {
          this.add(item, MEDIUM, "sort-after-search", "P5",
            "$sort after $search materializes every search hit before sorting. Use the $search " +
            "`sort` option instead.", { ref: "agg" });
        } else if (!(nxt === "$limit" || nxt === "$group") && !names.slice(i + 1, i + 3).includes("$limit")) {
          this.add(item, LOW, "sort-no-limit", "P6",
            "$sort is a blocking stage (100 MB per stage, then spills). Unless an index supplies " +
            "the order, follow it with $limit (top-k sort) or slim the stream first.", { ref: "agg" });
        }
      } else if (name === "$limit" && i > 0 && names[i - 1] === "$search") {
        const n = num(v);
        if (n !== null && n >= 1000) {
          this.add(item, MEDIUM, "search-overfetch", "P5",
            `$limit ${Math.trunc(n)} after $search over-fetches; size it to the page and use $searchMeta ` +
            "for counts.", { ref: "agg" });
        }
      } else if (name === "$group" && v.kind === "object") {
        this.group(stages, i, v);
      } else if (name === "$lookup" && v.kind === "object") {
        this.lookup(t, v, item);
      }
    });
    this.recommendPipeline(t, stages);
  }

  hoistMatch(arr, stages) {
    for (let i = 0; i < stages.length; i++) {
      const [name, v, item] = stages[i];
      if (name !== "$match" || i === 0 || v === null || v.kind !== "object") continue;
      const used = matchFields(v);
      if (used === null) continue;
      let j = i;
      while (j > 0 && TRANSPARENT.has(stages[j - 1][0]) && !intersects(produced(stages[j - 1]), used)) j -= 1;
      if (j === i) continue;
      const order = stages.map((s) => s[2]);
      order.splice(j, 0, order.splice(i, 1)[0]);
      const fix = stages.length === arr.items.length ? this.rebuildArray(arr, order) : null;
      const movedOver = stages.slice(j, i).map((s) => s[0]).join(", ");
      this.add([item.start, item.end], MEDIUM, "match-not-early", "P5",
        `This $match reads none of the fields produced by ${movedOver}, so it can run before them: ` +
        "fewer documents flow through the pipeline and, at the front, it can use an index.", { fix: null, ref: "agg" });
      if (fix !== null) {
        this.findings.push({ start: arr.start, end: arr.end, severity: MEDIUM, code: "match-not-early-rewrite", pass: "P5",
          message: "Move $match ahead of " + movedOver + ".", fix, ref: REFS.agg });
      }
      return;
    }
  }

  rebuildArray(arr, order) {
    const first = arr.items[0], last = arr.items[arr.items.length - 1];
    const inner = this.text.slice(first.start, last.end);
    let body;
    if (inner.includes("\n")) {
      const lineStart = this.text.lastIndexOf("\n", first.start - 1) + 1;
      const indent = this.text.slice(lineStart, first.start);
      body = order.map((n) => this.src(n)).join(",\n" + indent);
    } else {
      body = order.map((n) => this.src(n)).join(", ");
    }
    return this.text.slice(arr.start, first.start) + body + this.text.slice(last.end, arr.end);
  }

  group(stages, i, v) {
    const later = stages.slice(i + 1);
    for (const p of v.props) {
      if (p.key === "_id" || p.value === null || p.value.kind !== "object" || !p.value.props.length) continue;
      const acc = p.value.props[0];
      if (acc.value !== null && acc.value.kind === "string" && acc.value.value === "$$ROOT") {
        this.add(acc, acc.key === "$push" ? HIGH : MEDIUM, "group-root", "P5",
          `${acc.key}: "$$ROOT" carries whole documents into $group memory (100 MB per stage). ` +
          "$project only the fields you need first.", { ref: "agg" });
      }
      if (acc.key === "$push" && later.some((s) => slices(s, p.key))) {
        this.add(acc, HIGH, "push-then-slice", "P5",
          `${p.key} builds an unbounded array with $push and a later stage slices it. Use a bounded ` +
          "accumulator ($firstN / $lastN / $topN / $bottomN, 5.2+) so the discarded elements are " +
          "never held in memory.", { ref: "agg" });
      }
    }
    const prev = i > 0 ? stages[i - 1][0] : null;
    const accs = new Set(v.props.filter((p) => p.key !== "_id" && p.value !== null && p.value.kind === "object" && p.value.props.length)
      .map((p) => p.value.props[0].key));
    if (prev === "$sort" && accs.size && [...accs].every((a) => a === "$first" || a === "$last")) {
      this.add(stages[i][2], LOW, "distinct-scan-eligible", "P5",
        "$sort + $group with only $first/$last can run as a DISTINCT_SCAN (one index seek per group) " +
        "when an index matches the sort and group key — keep this shape and confirm with explain().", { ref: "planner" });
    } else if (i === 0) {
      this.add(stages[i][2], LOW, "group-whole-collection", "P5",
        "$group as the first stage reads the whole collection on every run. If this is a recurring " +
        "report, maintain a summary collection ($merge or on-write upsert).", { ref: "agg" });
    }
  }

  lookup(t, v, item) {
    const opts = new Map(v.props.map((p) => [p.key, p.value]));
    const frm = opts.get("from"), ff = opts.get("foreignField");
    if (frm && frm.kind === "string" && ff && ff.kind === "string" && ff.value !== "_id") {
      this.indexes.push(new IndexRec(String(frm.value), [[String(ff.value), 1]],
        `$lookup from ${t.collection} probes ${frm.value}.${ff.value} once per ` +
        "input document; without this index each probe is a collection scan."));
    } else if (opts.has("pipeline") && !opts.has("localField")) {
      this.add(item, LOW, "lookup-pipeline", "P5",
        "Correlated $lookup pipeline: make sure its $match uses $expr $eq on an indexed field of the " +
        "foreign collection (or use localField/foreignField with pipeline, 5.0+).", { ref: "agg" });
    }
  }

  recommend(t, preds, sort, proj, why = "") {
    if (t.filter !== null && t.filter.kind === "object") {
      const ors = t.filter.props.filter((p) => p.key === "$or" && p.value !== null && p.value.kind === "array");
      if (ors.length && !this.findings.some((f) => f.start === ors[0].start && f.code === "or-to-in")) {
        for (const b of ors[0].value.items) {
          if (b.kind === "object") {
            const bp = preds.concat(this.quietFilter(b));
            this.emit(t, bp, sort, proj, `$or branch ${this.src(b).slice(0, 60)}`);
          }
        }
        if (preds.length) return;
      }
    }
    this.emit(t, preds, sort, proj, why);
  }

  quietFilter(obj) {
    const saved = this.findings.length;
    const out = this.filter(obj, { hasSort: false, rooted: false });
    this.findings.length = saved;
    return out;
  }

  emit(t, preds, sort, proj, why) {
    const eq = uniq(preds.filter((p) => p.kind === "eq" || p.kind === "in").map((p) => p.field));
    let rng = uniq(preds.filter((p) => (p.kind === "range" || p.kind === "regex") && !eq.includes(p.field)).map((p) => p.field));
    const srt = [];
    if (sort && sort.kind === "object") {
      for (const p of sort.props) {
        const d = num(p.value);
        if ((d === 1 || d === -1) && !eq.includes(p.key)) srt.push([p.key, Math.trunc(d)]);
      }
    }
    const sortKeys = srt.map(([f]) => f);
    const bounded = rng.filter((f) => sortKeys.includes(f));
    rng = rng.filter((f) => !sortKeys.includes(f));
    const keys = eq.map((f) => [f, 1]).concat(srt.filter(([f]) => !eq.includes(f)));
    for (const f of rng) if (!keys.some(([k]) => k === f)) keys.push([f, 1]);
    if (!keys.length) return;
    const parts = [];
    if (eq.length) parts.push("equality " + eq.join(", "));
    if (srt.length) parts.push("sort " + srt.map(([f]) => f).join(", "));
    if (rng.length) parts.push("range " + rng.join(", "));
    let rationale = "ESR order: " + parts.join(" -> ") + ".";
    if (bounded.length) rationale += ` The sort key ${bounded.join(", ")} also serves its range predicate.`;
    if (srt.length && rng.length) {
      rationale += " If the range is far more selective than the sort saves, test the ERS order (range " +
        "before sort) with explain() at representative values.";
    }
    if (preds.some((p) => p.kind === "in") && srt.length) rationale += " $in under 201 values keeps the sort index-backed via SORT_MERGE.";
    const cover = projectionFields(proj);
    const keySet = new Set(keys.map(([k]) => k));
    if (cover.length && cover.every((c) => keySet.has(c)) && proj) {
      const excl = proj.props.some((p) => p.key === "_id" && num(p.value) === 0);
      rationale += " Covers the projection" + (excl ? "" : " if you add _id: 0") + " (PROJECTION_COVERED, 0 documents examined).";
    }
    if (why) rationale = `[${why}] ` + rationale;
    const rec = new IndexRec(t.collection, keys, rationale);
    if (keys.length === 1 && keys[0][0] === "_id") return;
    if (this.indexes.every((r) => r.shell() !== rec.shell())) this.indexes.push(rec);
  }

  recommendPipeline(t, stages) {
    if (!stages.length || !(stages[0][0] === "$match" || stages[0][0] === "$sort")) return;
    let preds = [];
    let sort = null;
    if (stages[0][0] === "$match" && stages[0][1] !== null && stages[0][1].kind === "object") {
      preds = this.quietFilter(stages[0][1]);
      if (stages.length > 1 && stages[1][0] === "$sort") sort = stages[1][1];
    } else {
      sort = stages[0][1];
    }
    const fake = { kind: "find", collection: t.collection, method: "aggregate", start: t.start, end: t.end,
      filter: null, projection: null, sort: null, pipeline: null, chain: new Map() };
    this.emit(fake, preds, sort, null, "leading $match/$sort");
  }
}

function evidenceFindings(ev, start, end) {
  const out = [];
  const add = (sev, code, msg, ref = "explain") =>
    out.push({ start, end: Math.max(end, start + 1), severity: sev, code, pass: "P9", message: msg, fix: null, ref: REFS[ref] });
  const numOf = (k) => (typeof ev[k] === "number" ? ev[k] : null);
  const plan = has.call(ev, "planSummary") ? String(ev.planSummary) : "";
  if (plan.includes("COLLSCAN")) {
    add(HIGH, "log-collscan", `The logged plan was ${plan}: every document was read. The index ` +
      "recommendations below target this query shape.");
  }
  const docs = numOf("docsExamined"), ret = numOf("nreturned");
  if (docs !== null && ret !== null && docs >= 10 * Math.max(ret, 1)) {
    const ratio = pyRound(docs / Math.max(ret, 1));
    add(docs >= 1000 ? HIGH : MEDIUM, "log-scan-ratio",
      `docsExamined ${fmt(docs)} vs nreturned ${fmt(ret)} (about ${fmt(ratio)}:1): the query reads far ` +
      "more documents than it returns. The target is close to 1:1.");
  }
  if (ev.hasSortStage === true) {
    add(MEDIUM, "log-blocking-sort", "hasSortStage: the result was sorted in memory (blocking sort, 100 MB " +
      "limit). Put the sort keys in the index right after the equality keys.");
  }
  if (ev.usedDisk === true) {
    add(MEDIUM, "log-spill", "usedDisk: a blocking stage spilled to disk. Slim the stream ($match / $project " +
      "earlier) before the sort or group instead of raising memory limits.", "planner");
  }
  if (ev.replanned === true) {
    const reason = ev.replanReason ? ` (${ev.replanReason})` : "";
    add(MEDIUM, "log-replanned", `replanned${reason}: the cached plan stopped fitting, a sign of near-tied ` +
      "indexes. Design one index that clearly wins for this shape.", "planner");
  }
  const dur = numOf("durationMillis"), cap = numOf("maxTimeMS");
  if (dur !== null && cap !== null && cap > 0 && dur >= 0.95 * cap) {
    add(LOW, "log-timeout-bound", `durationMillis ${fmt(dur)} is at the maxTimeMS ${fmt(cap)} cap: this is ` +
      "a timeout-bounded baseline, not the query's real latency.");
  }
  return out;
}

function applyFixes(text, findings) {
  const fixes = findings.filter((f) => f.fix !== null)
    .sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
  const chosen = [];
  let lastEnd = -1;
  for (const f of fixes) {
    if (f.start >= lastEnd) {
      chosen.push(f);
      lastEnd = f.end;
    }
  }
  for (const f of [...chosen].reverse()) text = text.slice(0, f.start) + f.fix + text.slice(f.end);
  return [text, chosen];
}

/** Audit every query in `text`; with apply, rewrite in place until nothing changes (cap maxIters). */
export function optimize(text, { apply = true, maxIters = 3 } = {}) {
  const norm = normalize(text);
  let current = norm.text;
  let applied = [];
  let iters = 0;
  let audit;
  let nInput = 0;
  for (;;) {
    iters += 1;
    audit = new Audit(current);
    audit.run();
    if (iters === 1) nInput = audit.targets.length;
    if (!apply || iters > maxIters) break;
    const [next, chosen] = applyFixes(current, audit.findings);
    if (!chosen.length || next === current) break;
    applied = applied.concat(chosen);
    current = next;
  }
  const evidence = norm.queries.map((q) => q.evidence);
  evidence.forEach((ev, i) => {
    if (Object.keys(ev).length) {
      const t = i < audit.targets.length ? audit.targets[i] : null;
      audit.findings.push(...evidenceFindings(ev, t ? t.start : 0, t ? t.end : 1));
    }
  });
  audit.findings.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || a.start - b.start);
  return {
    original: norm.text, text: current, targets: audit.targets, findings: audit.findings, applied,
    indexes: audit.indexes, iterations: iters, inputQueries: nInput, inputKind: norm.kind,
    interpreted: norm.changed ? norm.text : null, evidence,
    get changed() { return this.text !== this.original; },
  };
}

function countNl(t, off) {
  let n = 0;
  for (let i = 0; i < off; i++) if (t.charCodeAt(i) === 10) n++;
  return n;
}

function pos(t, off) {
  const lineStart = off > 0 ? t.lastIndexOf("\n", off - 1) + 1 : 0; // Python t.rfind("\n", 0, off) + 1
  return { line: countNl(t, off) + 1, column: off - lineStart + 1 };
}

/** Same structure as the Python to_dict(): the contract the golden files pin. */
export function toDict(rep) {
  const t = rep.text;
  return {
    input: { kind: rep.inputKind, interpreted: rep.interpreted },
    queries: rep.targets.map((x, i) => ({ kind: x.kind, collection: x.collection, method: x.method, ...pos(t, x.start),
      evidence: i < rep.evidence.length ? rep.evidence[i] : {} })),
    findings: rep.findings.filter((f) => !f.code.endsWith("-rewrite")).map((f) => ({ severity: f.severity, code: f.code,
      pass: f.pass, message: f.message, ref: f.ref, ...pos(t, f.start) })),
    applied: rep.applied.map((f) => ({ code: f.code, pass: f.pass, message: f.message })),
    indexes: rep.indexes.map((r) => ({ collection: r.collection, keys: Object.fromEntries(r.keys), shell: r.shell(),
      rationale: r.rationale })),
    rewritten: rep.changed ? rep.text : null,
    iterations: rep.iterations,
  };
}

const KIND_LABEL = { log: "slow-query log line", profile: "profiler entry", command: "command document",
  filter: "bare filter (collection name unknown)", pipeline: "bare pipeline (collection name unknown)" };

/** Human-readable report; byte-for-byte the same as the Python format_report(). */
export function formatReport(rep, name = "<input>") {
  const out = [];
  const t = rep.text;
  const counts = Object.keys(SEVERITY_ORDER).map((s) => [s, rep.findings.filter((f) => f.severity === s).length]);
  const countText = counts.filter(([, n]) => n).map(([s, n]) => `${n} ${s}`).join(", ") || "no open findings";
  out.push(`MQL optimizer (static audit) — ${name}: ${rep.inputQueries} quer${rep.inputQueries === 1 ? "y" : "ies"}, ` +
    countText + (rep.applied.length ? `; ${rep.applied.length} rewrite(s) applied in ${rep.iterations - 1} iteration(s)` : ""));
  if (rep.interpreted !== null) {
    const label = KIND_LABEL[rep.inputKind] ?? rep.inputKind;
    out.push(`\nInterpreted the input (${label}) as:\n` + rep.interpreted.trimEnd());
    rep.evidence.forEach((ev, i) => {
      if (Object.keys(ev).length) {
        const shown = ["planSummary", "durationMillis", "keysExamined", "docsExamined", "nreturned"]
          .filter((k) => has.call(ev, k)).map((k) => `${k}=${pyStr(ev[k])}`).join(", ");
        out.push(`  query ${i + 1} evidence: ${shown}`);
      }
    });
  }
  if (rep.applied.length) {
    out.push("\nApplied rewrites (result-preserving):");
    for (const f of rep.applied) out.push(`  ✓ [${f.pass} ${f.code}] ${f.message.split(". ")[0].replace(/\.+$/, "")}.`);
  }
  if (rep.findings.length) {
    out.push("\nFindings:");
    for (const f of rep.findings) {
      if (f.fix !== null && f.code.endsWith("-rewrite")) continue;
      const { line, column } = pos(t, f.start);
      out.push(`  ${name}:${line}:${column}: ${f.severity.toUpperCase()} [${f.pass} ${f.code}] ${f.message}`);
      if (f.ref) out.push(`      read more: mdbx show ${f.ref}`);
    }
  }
  if (rep.indexes.length) {
    out.push("\nRecommended indexes (recommend-only — build on non-prod first, check existing indexes):");
    for (const r of rep.indexes) out.push(`  ${r.shell()}\n      ${r.rationale}`);
  }
  if (rep.changed) out.push("\nRewritten query:\n" + rep.text.trimEnd());
  out.push("\nStatic analysis only: confirm with explain('executionStats') — COLLSCAN -> IXSCAN, " +
    "totalDocsExamined/nReturned near 1, nReturned unchanged.");
  return out.join("\n");
}

/** Python str() of an evidence value (True/False for booleans). */
function pyStr(v) {
  if (v === true) return "True";
  if (v === false) return "False";
  return String(v);
}
