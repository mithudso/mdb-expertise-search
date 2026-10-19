// normalize — turn what people paste from a case into mongosh calls the optimizer can audit.
// JavaScript port of mdbx/mql/normalize.py (the Python module documents the accepted inputs):
// mongosh calls, slow-query log lines, profiler entries, command documents, bare filters and
// bare pipelines. Log / profiler measurements are kept as `evidence` for the P9 findings.

import { parse } from "./parser.js";

const MONGOSH_CALL =
  /\bdb\s*(?:(?:\.\s*[A-Za-z_$][\w$]*|\[[^\]]*\])\s*\.\s*[A-Za-z_$][\w$]*\s*\(|\.\s*getCollection\s*\()/;
const IDENT_FULL = /^[A-Za-z_$][\w$]*$/;
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
  if (n.kind === "number") return n.value;
  if (n.kind === "string" || n.kind === "bool") return n.value;
  if (n.kind === "object") {
    const p = props(n);
    for (const k of ["$numberLong", "$numberInt", "$numberDouble"]) {
      if (p.has(k) && p.get(k).kind === "string") {
        const raw = String(p.get(k).value).trim();
        const f = Number(raw);
        if (raw === "" || Number.isNaN(f) && !/^nan$/i.test(raw)) return null;
        return f;
      }
    }
  }
  return null;
}

function collRef(name) {
  return IDENT_FULL.test(name) ? `db.${name}` : `db.getCollection(${pyJsonStr(name)})`;
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
      } else if (["$numberLong", "$numberInt", "$numberDouble"].includes(p.key) && v.kind === "string") rep = String(v.value);
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
  const res = [];
  let i = 0;
  let quote = null;
  while (i < s.length) {
    const ch = s[i];
    if (quote) {
      res.push(ch);
      if (ch === "\\" && i + 1 < s.length) {
        res.push(s[i + 1]);
        i += 2;
        continue;
      }
      if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'" || ch === "`") {
      quote = ch;
      res.push(ch);
    } else if (ch === "\r" || ch === "\n") {
      while (i + 1 < s.length && " \t\r\n".includes(s[i + 1])) i += 1;
      if (res.length && !" [{(".includes(res[res.length - 1])) res.push(" ");
    } else {
      res.push(ch);
    }
    i += 1;
  }
  return res.join("").trim();
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

function fromCommand(text, cmd, ns, kind, ev) {
  const c = props(cmd);
  const verb = VERBS.find((v) => c.has(v) && c.get(v).kind === "string") ?? null;
  let coll = verb ? String(c.get(verb).value) : null;
  if (coll === null && ns && ns.includes(".")) coll = ns.slice(ns.indexOf(".") + 1);
  if (verb === null || coll === null) return null;
  const db = collRef(coll);
  const L = (key, dflt = "{}") => (c.has(key) ? lit(text, c.get(key)) : dflt);
  let s;
  if (verb === "find") {
    const args = L("filter") + (c.has("projection") ? `, ${L("projection")}` : "");
    s = `${db}.find(${args})`;
    for (const [key, meth] of [["sort", "sort"], ["skip", "skip"], ["limit", "limit"], ["hint", "hint"],
      ["batchSize", "batchSize"]]) {
      if (c.has(key)) s += `.${meth}(${L(key)})`;
    }
  } else if (verb === "aggregate") {
    s = `${db}.aggregate(${L("pipeline", "[]")})`;
  } else if (verb === "count") {
    s = `${db}.count(${L("query")})`;
  } else if (verb === "distinct") {
    s = `${db}.distinct(${L("key", "''")}, ${L("query")})`;
  } else if (verb === "update") {
    const ups = c.get("updates");
    const first = ups && ups.kind === "array" && ups.items.length ? ups.items[0] : null;
    const u = props(first);
    if (!u.has("q")) return null;
    const multi = u.has("multi") && u.get("multi").kind === "bool" && u.get("multi").value;
    s = `${db}.${multi ? "updateMany" : "updateOne"}(${lit(text, u.get("q"))}, ${u.has("u") ? lit(text, u.get("u")) : "{}"})`;
  } else if (verb === "delete") {
    const dels = c.get("deletes");
    const first = dels && dels.kind === "array" && dels.items.length ? dels.items[0] : null;
    const d = props(first);
    if (!d.has("q")) return null;
    const one = d.has("limit") && d.get("limit").kind === "number" && d.get("limit").value === 1;
    s = `${db}.${one ? "deleteOne" : "deleteMany"}(${lit(text, d.get("q"))})`;
  } else {
    const remove = c.has("remove") && c.get("remove").kind === "bool" && c.get("remove").value;
    const sort = c.has("sort") ? `, { sort: ${L("sort")} }` : "";
    s = remove ? `${db}.findOneAndDelete(${L("query")}${sort})` : `${db}.findOneAndUpdate(${L("query")}, ${L("update")}${sort})`;
  }
  return { text: s, kind, collection: coll, evidence: ev };
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
      const db = collRef(coll);
      let s;
      if (op === "update") {
        const multi = c.has("multi") && c.get("multi").kind === "bool" && c.get("multi").value;
        const upd = c.has("u") ? lit(text, c.get("u")) : "{}";
        s = `${db}.${multi ? "updateMany" : "updateOne"}(${lit(text, c.get("q"))}, ${upd})`;
      } else {
        const one = c.has("limit") && c.get("limit").kind === "number" && c.get("limit").value === 1;
        s = `${db}.${one ? "deleteOne" : "deleteMany"}(${lit(text, c.get("q"))})`;
      }
      return { text: s, kind: "profile", collection: coll, evidence: ev };
    }
    return fromCommand(text, cmd, ns, "profile", ev);
  }
  if (VERBS.some((v) => top.has(v) && top.get(v).kind === "string")) return fromCommand(text, node, null, "command", {});
  if (node.props.length) return { text: `db.${PLACEHOLDER}.find(${lit(text, node)})`, kind: "filter", collection: null, evidence: {} };
  return null;
}

/** Returns { text, kind, queries, changed }. */
export function normalize(text) {
  if (MONGOSH_CALL.test(text)) return { text, kind: "mongosh", queries: [], changed: false };
  const [statements] = parse(text);
  const queries = [];
  for (const st of statements) {
    const node = st.node;
    let q = null;
    if (node.kind === "object") {
      q = fromObject(text, node);
    } else if (node.kind === "array" && node.items.length &&
      node.items.every((i) => i.kind === "object" && i.props.length === 1 && i.props[0].key.startsWith("$"))) {
      q = { text: `db.${PLACEHOLDER}.aggregate(${lit(text, node)})`, kind: "pipeline", collection: null, evidence: {} };
    }
    if (q !== null) queries.push(q);
  }
  if (!queries.length) return { text, kind: "mongosh", queries: [], changed: false };
  return { text: queries.map((q) => q.text).join("\n") + "\n", kind: queries[0].kind, queries, changed: true };
}
