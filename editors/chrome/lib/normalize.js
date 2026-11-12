// normalize — turn what people paste from a case into mongosh calls the optimizer can audit.
// JavaScript port of mdbx/mql/normalize.py (the Python module documents the accepted inputs):
// mongosh calls, slow-query log lines, profiler entries, command documents, bare filters and
// bare pipelines. Log / profiler measurements are kept as `evidence` for the P9 findings.
// Unsafe int64 evidence uses exact decimal strings in both ports; nonfinite measurements are omitted.

import { parse } from "./parser.js";

const INTEGER = /^-?(?:0|[1-9][0-9]*)$/;
const DOUBLE = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$/;
const META = new Set(["$db", "lsid", "$clusterTime"]);
const VERBS = ["find", "aggregate", "count", "distinct", "update", "delete", "findAndModify", "findandmodify"];
export const EVIDENCE_KEYS = ["planSummary", "keysExamined", "docsExamined", "nreturned", "durationMillis",
  "hasSortStage", "usedDisk", "replanned", "replanReason", "fromMultiPlanner", "queryFramework",
  "planCacheShapeHash", "queryShapeHash", "queryHash", "planCacheKey"];
export const PLACEHOLDER = "collection";

/** Python json.dumps(str): JSON with non-ASCII escaped as \uXXXX. */
export function pyJsonStr(s) {
  return JSON.stringify(s).replace(/[\u0080-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
}

function props(node) {
  const out = new Map();
  if (!node || node.kind !== "object") return out;
  for (const p of node.props) if (p.value !== null) out.set(p.key, p.value);
  return out;
}

function str(n) {
  return n && n.kind === "string" ? String(n.value) : null;
}

function isIntegral(v) {
  return typeof v === "number" && Number.isFinite(v) && Number.isInteger(v);
}

export function scalar(n) {
  if (n.kind === "number") {
    if (n.exactInteger !== undefined && !Number.isSafeInteger(n.value)) return n.exactInteger;
    return Number.isFinite(n.value) ? (Number.isInteger(n.value) && !Number.isSafeInteger(n.value) ? BigInt(n.value).toString() : n.value) : null;
  }
  if (n.kind === "string" || n.kind === "bool") return n.value;
  if (n.kind === "object") {
    const p = props(n);
    if (p.size === 1) {
      const [k, value] = [...p][0];
      if (value.kind === "string") {
        const decoded = numericWrapper(k, String(value.value));
        return typeof decoded === "number" && Number.isInteger(decoded) && !Number.isSafeInteger(decoded) ? BigInt(decoded).toString() : decoded;
      }
    }
  }
  return null;
}

function numericWrapper(key, raw) {
  if (key === "$numberLong" || key === "$numberInt") {
    if (raw.length > 20 || !INTEGER.test(raw)) return null;
    const value = BigInt(raw), bits = key === "$numberLong" ? 64n : 32n;
    if (value < -(1n << (bits - 1n)) || value >= (1n << (bits - 1n))) return null;
    const number = Number(value);
    return Number.isSafeInteger(number) ? number : value.toString();
  }
  if (key === "$numberDouble" && DOUBLE.test(raw)) {
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }
  return null;
}

export function collRef(name) {
  return `db.getCollection(${pyJsonStr(name)})`;
}

function evidence(src, cmd) {
  const ev = {};
  for (const k of EVIDENCE_KEYS) {
    if (src.has(k)) {
      const v = scalar(src.get(k));
      if (v !== null) ev[k] = v;
    }
  }
  if (!("durationMillis" in ev) && src.has("millis") && scalar(src.get("millis")) !== null) {
    ev.durationMillis = scalar(src.get("millis"));
  }
  if (cmd.has("maxTimeMS") && scalar(cmd.get("maxTimeMS")) !== null) ev.maxTimeMS = scalar(cmd.get("maxTimeMS"));
  return ev;
}

function fmtScalar(v) {
  return isIntegral(v) ? String(v) : String(v);
}

// ---- literal copying with extended-JSON conversion

function ejsonEdits(text, node, edits) {
  if (node.kind === "object" && node.props.length === 1) {
    const p = node.props[0];
    const v = p.value;
    let rep = null;
    if (v !== null) {
      const vs = text.slice(v.start, v.end);
      if (p.key === "$oid" && v.kind === "string") rep = `ObjectId(${vs})`;
      else if (p.key === "$date" && v.kind === "string") rep = `ISODate(${vs})`;
      else if (p.key === "$date" && v.kind === "number") rep = `new Date(${vs})`;
      else if (p.key === "$date" && v.kind === "object") {
        const inner = scalar(v);
        rep = inner !== null ? `new Date(${fmtScalar(inner)})` : null;
      } else if (["$numberLong", "$numberInt", "$numberDouble"].includes(p.key) && v.kind === "string") {
        const value = numericWrapper(p.key, String(v.value));
        if (value !== null) rep = p.key === "$numberLong" ? `NumberLong(${pyJsonStr(String(v.value))})` : String(v.value);
      }
      else if (p.key === "$numberDecimal" && v.kind === "string") rep = `NumberDecimal(${vs})`;
    }
    if (rep !== null) {
      edits.push([node.start, node.end, rep]);
      return;
    }
  }
  for (const p of node.props) if (p.value !== null) ejsonEdits(text, p.value, edits);
  for (const it of node.items) ejsonEdits(text, it, edits);
}

function oneLine(s) {
  // A comment's line ending is significant. Keep the original layout when markers occur.
  if (s.includes("//") || s.includes("/*")) return s.trim();
  const [statements, errors] = parse(s);
  if (errors.length) return s.trim();
  const protectedSpans = [];
  for (const statement of statements) {
    for (const node of statement.node.walk()) {
      if (node.kind === "string" || node.kind === "regex") protectedSpans.push([node.start, node.end]);
      for (const prop of node.props) if (prop.quoted) protectedSpans.push([prop.keyStart, prop.keyEnd]);
    }
  }
  protectedSpans.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const out = [];
  let position = 0;
  const copyGap = (end) => {
    while (position < end) {
      const ch = s[position];
      if ("\r\n\u2028\u2029".includes(ch)) {
        while (position + 1 < end && " \t\r\n".includes(s[position + 1])) position += 1;
        if (out.length && !" [{(".includes(out[out.length - 1].at(-1))) out.push(" ");
      } else out.push(ch);
      position += 1;
    }
  };
  for (const [start, end] of protectedSpans) {
    if (start < position) continue;
    copyGap(start);
    out.push(s.slice(start, end));
    position = end;
  }
  copyGap(s.length);
  return out.join("").trim();
}

function lit(text, node) {
  const edits = [];
  ejsonEdits(text, node, edits);
  edits.sort((a, b) => a[0] - b[0] || a[1] - b[1] || (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0));
  const out = [];
  let pos = node.start;
  for (const [s, e, rep] of edits) {
    if (s < pos) continue;
    out.push(text.slice(pos, s), rep);
    pos = e;
  }
  out.push(text.slice(pos, node.end));
  return oneLine(out.join(""));
}

// ---- commands

function options(text, c, keys) {
  const body = keys.filter((key) => c.has(key)).map((key) => `${key}: ${lit(text, c.get(key))}`).join(", ");
  return body ? `, {${body}}` : "";
}

function writeCall(text, db, c, verb, shared = new Map()) {
  const optionKeys = verb === "update" ?
    ["upsert", "arrayFilters", "collation", "hint", "let", "writeConcern", "bypassDocumentValidation", "comment"] :
    ["collation", "hint", "let", "writeConcern", "comment"];
  const allowed = new Set([...(verb === "update" ? ["q", "u", "multi"] : ["q", "limit"]), ...optionKeys]);
  if ([...c.keys()].some((key) => !allowed.has(key)) || !c.has("q")) return null;
  const opts = new Map(shared);
  for (const key of optionKeys) if (c.has(key)) opts.set(key, c.get(key));
  let args = lit(text, c.get("q")), method;
  if (verb === "update") {
    if (!c.has("u") || (c.has("multi") && c.get("multi").kind !== "bool")) return null;
    const update = c.get("u");
    const replacement = update.kind === "object" && !update.props.some((p) => p.key.startsWith("$"));
    if (update.kind !== "object" && update.kind !== "array") return null;
    const multi = c.has("multi") && c.get("multi").value === true;
    if (replacement && multi) return null;
    method = replacement ? "replaceOne" : multi ? "updateMany" : "updateOne";
    args += ", " + lit(text, update);
  } else {
    const limit = c.has("limit") ? scalar(c.get("limit")) : null;
    if (limit !== 0 && limit !== 1) return null;
    method = limit === 1 ? "deleteOne" : "deleteMany";
  }
  return `${db}.${method}(${args}${options(text, opts, optionKeys)})`;
}

function batch(text, c, db, coll, verb, key, kind, ev) {
  const operations = c.get(key);
  if (!operations || operations.kind !== "array" || !operations.items.length) return null;
  const sharedKeys = new Set(["let", "writeConcern", "bypassDocumentValidation", "comment"]);
  const shared = new Map([...c].filter(([k]) => sharedKeys.has(k)));
  const queries = [];
  for (const operation of operations.items) {
    if (operation.kind !== "object") return null;
    const s = writeCall(text, db, props(operation), verb, shared);
    if (s === null) return null;
    queries.push({ text: s, kind, collection: coll, evidence: operations.items.length === 1 ? ev : {} });
  }
  return queries;
}

function fromCommand(text, cmd, ns, kind, ev) {
  const c = props(cmd);
  const verb = VERBS.find((v) => c.has(v) && c.get(v).kind === "string") ?? null;
  let coll = verb ? String(c.get(verb).value) : null;
  if (coll === null && ns && ns.includes(".")) coll = ns.slice(ns.indexOf(".") + 1);
  if (verb === null || coll === null) return null;
  const db = collRef(coll);
  const L = (key, dflt = "{}") => (c.has(key) ? lit(text, c.get(key)) : dflt);
  const allowed = {
    find: ["filter", "projection", "sort", "skip", "limit", "hint", "batchSize", "collation", "maxTimeMS", "comment", "min", "max", "returnKey", "showRecordId", "allowDiskUse"],
    aggregate: ["pipeline", "cursor", "allowDiskUse", "maxTimeMS", "collation", "hint", "let", "comment", "readConcern", "writeConcern", "bypassDocumentValidation"],
    count: ["query", "skip", "limit", "hint", "collation", "maxTimeMS", "comment", "readConcern"],
    distinct: ["key", "query", "collation", "maxTimeMS", "comment", "readConcern"],
    update: ["updates", "let", "writeConcern", "bypassDocumentValidation", "comment"],
    delete: ["deletes", "let", "writeConcern", "comment"],
    findAndModify: ["query", "sort", "remove", "update", "new", "fields", "upsert", "collation", "arrayFilters", "hint", "let", "maxTimeMS", "writeConcern", "bypassDocumentValidation", "comment"],
  };
  const canonical = verb === "findandmodify" ? "findAndModify" : verb;
  if ([...c.keys()].some((key) => key !== verb && !META.has(key) && !allowed[canonical].includes(key))) return null;
  let s;
  if (verb === "find") {
    const args = L("filter") + (c.has("projection") ? `, ${L("projection")}` : "");
    s = `${db}.find(${args})`;
    for (const [key, meth] of [["sort", "sort"], ["skip", "skip"], ["limit", "limit"], ["hint", "hint"],
      ["batchSize", "batchSize"], ["collation", "collation"], ["maxTimeMS", "maxTimeMS"], ["comment", "comment"],
      ["min", "min"], ["max", "max"], ["returnKey", "returnKey"], ["showRecordId", "showRecordId"], ["allowDiskUse", "allowDiskUse"]]) {
      if (c.has(key)) s += `.${meth}(${L(key)})`;
    }
  } else if (verb === "aggregate") {
    const opts = new Map([...c].filter(([key]) => allowed.aggregate.includes(key) && !["pipeline", "cursor"].includes(key)));
    if (c.has("cursor")) {
      const cursor = props(c.get("cursor"));
      if (c.get("cursor").kind !== "object" || [...cursor.keys()].some((key) => key !== "batchSize")) return null;
      for (const [key, value] of cursor) opts.set(key, value);
    }
    s = `${db}.aggregate(${L("pipeline", "[]")}${options(text, opts, [...opts.keys()].sort())})`;
  } else if (verb === "count") {
    s = `${db}.count(${L("query")}${options(text, c, ["skip", "limit", "hint", "collation", "maxTimeMS", "comment", "readConcern"])})`;
  } else if (verb === "distinct") {
    s = `${db}.distinct(${L("key", "''")}, ${L("query")}${options(text, c, ["collation", "maxTimeMS", "comment", "readConcern"])})`;
  } else if (verb === "update") {
    return batch(text, c, db, coll, verb, "updates", kind, ev);
  } else if (verb === "delete") {
    return batch(text, c, db, coll, verb, "deletes", kind, ev);
  } else {
    const remove = c.has("remove") && c.get("remove").kind === "bool" && c.get("remove").value;
    const opts = new Map([...c].filter(([key]) => allowed.findAndModify.includes(key) && !["query", "remove", "update", "new", "fields"].includes(key)));
    if (c.has("fields")) opts.set("projection", c.get("fields"));
    if (c.has("new")) opts.set("returnNewDocument", c.get("new"));
    let suffix = options(text, opts, [...opts.keys()]);
    if (opts.size === 1 && opts.has("sort")) suffix = `, { sort: ${L("sort")} }`;
    if (remove) {
      if (["update", "upsert", "new", "arrayFilters"].some((key) => c.has(key))) return null;
      s = `${db}.findOneAndDelete(${L("query")}${suffix})`;
    } else {
      const update = c.get("update");
      if (!update || (update.kind !== "object" && update.kind !== "array")) return null;
      const replacement = update.kind === "object" && !update.props.some((p) => p.key.startsWith("$"));
      s = `${db}.${replacement ? "findOneAndReplace" : "findOneAndUpdate"}(${L("query")}, ${L("update")}${suffix})`;
    }
  }
  return [{ text: s, kind, collection: coll, evidence: ev }];
}

function fromObject(text, node) {
  const top = props(node);
  const attr = props(top.get("attr"));
  if (attr.size && (attr.has("command") || attr.has("originatingCommand"))) {
    let cmd = attr.get("command") ?? null;
    if (attr.has("originatingCommand") && (cmd === null || props(cmd).has("getMore"))) cmd = attr.get("originatingCommand");
    return fromCommand(text, cmd, str(attr.get("ns")), "log", evidence(attr, props(cmd)));
  }
  if (top.has("op") && top.has("ns") && (top.has("command") || top.has("originatingCommand"))) {
    let cmd = top.get("command") ?? null;
    if (top.has("originatingCommand") && (cmd === null || props(cmd).has("getMore"))) cmd = top.get("originatingCommand");
    const ev = evidence(top, props(cmd));
    const ns = str(top.get("ns"));
    const c = props(cmd);
    const op = str(top.get("op"));
    if (["update", "remove", "delete"].includes(op) && c.has("q") && ns && ns.includes(".")) {
      const coll = ns.slice(ns.indexOf(".") + 1);
      const s = writeCall(text, collRef(coll), c, op === "update" ? "update" : "delete");
      return s !== null ? [{ text: s, kind: "profile", collection: coll, evidence: ev }] : null;
    }
    return fromCommand(text, cmd, ns, "profile", ev);
  }
  if (VERBS.some((v) => top.has(v) && top.get(v).kind === "string")) return fromCommand(text, node, null, "command", {});
  return [{ text: `db.${PLACEHOLDER}.find(${lit(text, node)})`, kind: "filter", collection: null, evidence: {} }];
}

function dbCall(node) {
  if (node.kind !== "call") return false;
  while (node.target !== null && (node.kind === "call" || node.kind === "member")) node = node.target;
  return node.kind === "ident" && node.value === "db";
}

/** Returns { text, kind, queries, changed }. */
export function normalize(text) {
  const [statements, errors] = parse(text);
  if (statements.some((st) => dbCall(st.node))) return { text, kind: "mongosh", queries: [], changed: false };
  const queries = [];
  let unknown = errors.length > 0;
  const intervals = [...errors].sort((a, b) => a.start - b.start);
  let errorIndex = 0;
  for (const st of statements) {
    const node = st.node;
    if (st.decl) return { text, kind: "mongosh", queries: [], changed: false };
    if (node.kind !== "object" && node.kind !== "array") { unknown = true; continue; }
    while (errorIndex < intervals.length && intervals[errorIndex].end <= node.start) errorIndex++;
    if (errorIndex < intervals.length && intervals[errorIndex].start < node.end) return { text, kind: "mongosh", queries: [], changed: false };
    let q = null;
    if (node.kind === "object") {
      q = fromObject(text, node);
    } else if (node.kind === "array" &&
      node.items.every((i) => i.kind === "object" && i.props.length === 1 && i.props[0].key.startsWith("$"))) {
      q = [{ text: `db.${PLACEHOLDER}.aggregate(${lit(text, node)})`, kind: "pipeline", collection: null, evidence: {} }];
    }
    if (q === null) return { text, kind: "mongosh", queries: [], changed: false };
    for (const query of q) queries.push(query);
  }
  if (!queries.length || (unknown && queries.some((q) => q.kind !== "log" && q.kind !== "profile"))) return { text, kind: "mongosh", queries: [], changed: false };
  return { text: queries.map((q) => q.text).join("\n") + "\n", kind: queries[0].kind, queries, changed: true };
}
