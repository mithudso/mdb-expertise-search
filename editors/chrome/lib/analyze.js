// analyze — context-aware lint over the MQL tree. JavaScript port of mdbx/mql/analyze.py.
//
// The analyzer assigns every object it understands a context label (query, qops, expr, fields,
// group, update, upmods, pipeline-item, ...). Diagnostics come from validating keys and arguments
// against that context. Completion and hover (mdbx/mql/features.py) are not ported.
//
// The Python module is the reference. tests/fixtures/lint/*.lint.json pins its output and
// editors/chrome/test/lint-parity.test.mjs checks this port against every golden file. Messages,
// codes, severities, fixes and ordering are byte-identical, including Python repr() quoting of keys.

import { Node, Prop, parse, pyRepr } from "./parser.js";
import * as ops from "./operators.js";

export { Node, Prop, pyRepr };
export const ERROR = "error", WARNING = "warning", INFO = "info", HINT = "hint";

/** Method name -> context of each positional argument ("-" = not analysed). */
const METHODS = new Map(Object.entries({
  find: ["query", "proj"], findOne: ["query", "proj"], countDocuments: ["query"],
  count: ["query"], distinct: ["-", "query"], deleteOne: ["query"], deleteMany: ["query"],
  remove: ["query"], findOneAndDelete: ["query"],
  findOneAndUpdate: ["query", "update"], updateOne: ["query", "update"],
  updateMany: ["query", "update"], update: ["query", "update"],
  findOneAndReplace: ["query", "-"], replaceOne: ["query", "-"],
  aggregate: ["pipeline"], watch: ["pipeline"],
  sort: ["sort"], project: ["proj"], projection: ["proj"],
}));

const KIND_NAMES = {
  object: "an object", array: "an array", "array+": "a non-empty array",
  array2: "an array of exactly 2 elements", string: "a string", bool: "a boolean",
  int: "an integer", posint: "a positive integer", nonneg: "a non-negative integer",
  number: "a number",
};
const kindName = (k) => (Object.prototype.hasOwnProperty.call(KIND_NAMES, k) ? KIND_NAMES[k] : k);
const DYNAMIC = new Set(["call", "ident", "member", "error"]);
const dyn = (kind) => DYNAMIC.has(kind);
const dynOr = (...kinds) => new Set([...kinds, ...DYNAMIC]);
const SORT_WORDS = new Set(["asc", "desc", "ascending", "descending"]);
const FREE_FORM = new Set(["$sortByCount", "$redact", "$replaceWith", "$unionWith", "$out", "$merge", "$unwind", "$unset"]);
const TEXT_KEYS = new Set(["$search", "$language", "$caseSensitive", "$diacriticSensitive"]);

// ---- Python-compatible helpers ---------------------------------------------------------------------

/** Python float() of a number node's value; null for anything else. */
function num(node) {
  return node !== null && node.kind === "number" ? Number(node.value) : null;
}

/** Python bool(value) for a number/bool node value. */
function truthy(v) {
  if (typeof v === "number") return v !== 0; // bool(nan) is True in Python
  if (typeof v === "string") return v.length > 0;
  return Boolean(v);
}

function kindOk(node, kind) {
  if (dyn(node.kind)) return true;
  for (const k of kind.split("|")) {
    if (k === "any") return true;
    if (k === "object" && node.kind === "object") return true;
    if (k === "array" && node.kind === "array") return true;
    if (k === "array+" && node.kind === "array" && node.items.length) return true;
    if (k === "array2" && node.kind === "array" && node.items.length === 2) return true;
    if (k === "string" && node.kind === "string") return true;
    if (k === "bool" && (node.kind === "bool" || node.kind === "number")) return true;
    if ((k === "int" || k === "posint" || k === "nonneg" || k === "number") && node.kind === "number") {
      const v = Number(node.value);
      if (k === "number") return true;
      if (!Number.isInteger(v)) continue;
      if (k === "posint" && v <= 0) continue;
      if (k === "nonneg" && v < 0) continue;
      return true;
    }
  }
  return false;
}

export class Symbol_ {
  constructor(name, kind, start, end, children = []) {
    Object.assign(this, { name, kind, start, end, children });
  }
}

/** Line (0-based) and UTF-16 column of an offset, as mdbx.mql.server.offset_to_position. */
export function offsetToPosition(text, offset) {
  offset = Math.max(0, Math.min(offset, text.length));
  let line = 0;
  for (let i = text.indexOf("\n"); i >= 0 && i < offset; i = text.indexOf("\n", i + 1)) line += 1;
  const lineStart = offset > 0 ? text.lastIndexOf("\n", offset - 1) + 1 : 0;
  return { line, column: offset - lineStart };
}

class Analyzer {
  constructor(text) {
    this.text = text;
    const [statements, perrs] = parse(text);
    this.statements = statements;
    this.diags = perrs.map((e) => ({ start: e.start, end: e.end, severity: ERROR, code: "syntax", message: e.message, fix: null }));
    this.objects = [];
    this.arrays = [];
    this.stageSyms = new Map();
    this.done = new Set();
    this.varCtx = new Map();
    this.vars = new Map();
  }

  // ---- reporting
  add(start, end, sev, code, msg, fix = null) {
    this.diags.push({ start, end: Math.max(end, start + 1), severity: sev, code, message: msg, fix });
  }

  onProp(p, sev, code, msg, fix = null) {
    this.add(p.keyStart, p.keyEnd, sev, code, msg, fix);
  }

  unknown(p, want = "operator") {
    const sug = ops.suggest(p.key);
    if (sug.length) {
      this.onProp(p, ERROR, "unknown-operator", `Unknown ${want} ${p.key}. Did you mean ${sug[0]}?`, sug[0]);
    } else {
      this.onProp(p, WARNING, "unknown-operator",
        `${p.key} is not in the built-in operator table (it may be newer than this server).`);
    }
  }

  dups(obj) {
    const seen = new Set();
    for (const p of obj.props) {
      if (seen.has(p.key)) {
        this.onProp(p, WARNING, "duplicate-key",
          `Duplicate key ${pyRepr(p.key)}: the later value silently replaces the earlier one.`);
      }
      seen.add(p.key);
    }
  }

  /** Validate the argument of `op`. Returns whether it is acceptable. */
  arg(p, op) {
    const v = p.value;
    if (v === null) return true;
    if (kindOk(v, op.arg)) return true;
    const want = op.arg.split("|").map(kindName).join(" or ");
    this.add(v.start, v.end, ERROR, "bad-argument", `${op.name} expects ${want}, got ${v.kind}.`);
    return false;
  }

  // ---- entry
  run() {
    this.collectVars();
    for (const st of this.statements) {
      const node = st.node;
      if (st.decl) this.vars.set(st.decl, node);
      const ctx = this.varCtx.get(st.decl || "");
      if (ctx && !this.done.has(node)) this.value(node, ctx);
      else if (!this.done.has(node)) this.statementNode(node);
      for (const c of node.walk()) {
        if (c.kind === "call" && !this.done.has(c)) this.call(c);
      }
    }
    this.diags.sort((a, b) => (a.start - b.start) || (a.end - b.end)); // stable, like Python's sort
    return {
      text: this.text, statements: this.statements, diagnostics: this.diags,
      objects: this.objects, arrays: this.arrays, symbols: this.symbols(),
    };
  }

  collectVars() {
    for (const st of this.statements) {
      for (const c of st.node.walk()) {
        if (c.kind !== "call" || c.target === null || c.target.kind !== "member") continue;
        const spec = METHODS.get(String(c.target.value));
        if (!spec) continue;
        c.items.forEach((a, i) => {
          if (a.kind === "ident" && i < spec.length && spec[i] !== "-" && !this.varCtx.has(String(a.value))) {
            this.varCtx.set(String(a.value), spec[i]);
          }
        });
      }
    }
  }

  statementNode(node) {
    if (node.kind === "array" || node.kind === "object") this.value(node, "auto");
    else if (node.kind === "call") this.call(node);
  }

  call(c) {
    this.done.add(c);
    if (c.target === null || c.target.kind !== "member") return;
    const spec = METHODS.get(String(c.target.value));
    if (!spec) return;
    c.items.forEach((a, i) => {
      if (i < spec.length && spec[i] !== "-") {
        if (a.kind === "ident" && this.vars.has(String(a.value))) return; // analysed at its declaration
        this.value(a, spec[i]);
      }
    });
  }

  // ---- dispatch
  value(node, ctx) {
    if (this.done.has(node)) return;
    this.done.add(node);
    if (ctx === "pipeline") {
      this.pipeline(node);
    } else if (ctx === "query") {
      if (this.need(node, "object", "a query document")) this.query(node);
    } else if (ctx === "update") {
      if (node.kind === "array") this.pipeline(node, { update: true });
      else if (this.need(node, "object", "an update document")) this.update(node);
    } else if (ctx === "proj") {
      if (node.kind === "object") this.fields(node, { project: true, label: "proj" });
    } else if (ctx === "sort") {
      if (node.kind === "object") this.sort(node, { strictStrings: false });
    } else if (ctx === "auto") {
      this.auto(node);
    }
  }

  need(node, kind, what) {
    if (dyn(node.kind) || node.kind === kind) return node.kind === kind;
    this.add(node.start, node.end, ERROR, "bad-argument", `Expected ${what}, got ${node.kind}.`);
    return false;
  }

  auto(node) {
    if (node.kind === "array") {
      if (this.looksLikePipeline(node)) this.pipeline(node);
      return;
    }
    if (node.kind !== "object" || !node.props.length) return;
    const keys = node.props.map((p) => p.key);
    if (keys.length === 1 && ops.STAGES.has(keys[0]) && !ops.UPDATE_OPS.has(keys[0])) {
      this.stage(node, 0, true, false, false, true);
    } else if (keys.every((k) => ops.UPDATE_OPS.has(k) || (ops.OPERATORS.has(k) && ops.OPERATORS.get(k).cats.has("removed")))) {
      this.update(node, { requireOps: false });
    } else {
      this.query(node, { lenient: true });
    }
  }

  looksLikePipeline(arr) {
    return arr.items.length > 0 && arr.items.every(
      (i) => i.kind === "object" && i.props.length === 1 && ops.STAGES.has(i.props[0].key));
  }

  // ---- query documents
  query(obj, { inMatch = false, first = false, lenient = false } = {}) {
    this.objects.push([obj, "query"]);
    this.dups(obj);
    for (const p of obj.props) {
      const v = p.value;
      if (p.key.startsWith("$")) {
        const op = ops.get(p.key);
        if (op === null) {
          this.unknown(p);
        } else if (op.cats.has("qtop")) {
          this.queryTop(p, op, inMatch, first);
        } else if (op.isA("ejson") || (lenient && op.isA("expr", "acc", "stage", "update"))) {
          // accepted
        } else if (op.isA("query")) {
          this.onProp(p, WARNING, "misplaced-operator",
            `${p.key} is a field operator; put it inside a field: { field: { ${p.key}: … } }.`);
        } else {
          this.onProp(p, WARNING, "misplaced-operator", `${p.key} is not a query operator here.`);
        }
      } else if (v !== null && v.kind === "object") {
        this.fieldValue(v);
      }
    }
  }

  queryTop(p, op, inMatch, first) {
    const v = p.value;
    const name = p.key;
    if (name === "$and" || name === "$or" || name === "$nor") {
      if (v === null) return;
      if (v.kind === "array") {
        if (!v.items.length) this.add(v.start, v.end, ERROR, "bad-argument", `${name} requires a non-empty array.`);
        for (const it of v.items) {
          if (it.kind === "object") this.query(it, { inMatch, first });
          else if (!dyn(it.kind)) this.add(it.start, it.end, ERROR, "bad-argument", `Each ${name} element must be an object.`);
        }
      } else if (!dyn(v.kind)) {
        this.add(v.start, v.end, ERROR, "bad-argument", `${name} expects a non-empty array.`);
      }
    } else if (name === "$expr") {
      if (v !== null) this.expr(v);
    } else if (name === "$text") {
      if (inMatch && !first) this.onProp(p, ERROR, "stage-position", "$text is only allowed in the first stage of a pipeline.");
      if (v !== null && v.kind === "object") {
        this.objects.push([v, "text"]);
        const keys = new Set(v.props.map((q) => q.key));
        if (!keys.has("$search")) this.add(v.start, v.end, ERROR, "missing-field", "$text requires a $search string.");
        for (const q of v.props) {
          if (!TEXT_KEYS.has(q.key)) this.onProp(q, WARNING, "unknown-operator", `${q.key} is not a $text option.`);
        }
      } else if (v !== null && !dyn(v.kind)) {
        this.add(v.start, v.end, ERROR, "bad-argument", "$text expects an object with $search.");
      }
    } else if (name === "$where") {
      this.onProp(p, WARNING, "perf",
        "$where runs JavaScript per document, cannot use indexes and is an injection risk; " +
        "prefer $expr or regular operators.");
      if (inMatch) this.onProp(p, ERROR, "misplaced-operator", "$where is not allowed in a $match stage.");
    } else if (name === "$sampleRate") {
      const n = num(v);
      if (v !== null && v.kind === "number" && !(0 <= (n === null ? 0 : n) && (n === null ? 0 : n) <= 1)) {
        this.add(v.start, v.end, ERROR, "bad-argument", "$sampleRate must be between 0 and 1.");
      }
    }
  }

  fieldValue(obj) {
    const keys = obj.props.map((p) => p.key);
    const dollar = keys.filter((k) => k.startsWith("$"));
    if (!dollar.length) return; // embedded-document equality
    if (dollar.every((k) => ops.get(k) && ops.OPERATORS.get(k).isA("ejson")) && dollar.length === keys.length) return;
    for (const p of obj.props.filter((q) => !q.key.startsWith("$"))) {
      this.onProp(p, ERROR, "mixed-keys",
        `${pyRepr(p.key)} is a field name inside an operator expression; ` +
        "operators and field names cannot be mixed.");
    }
    this.qops(obj);
  }

  qops(obj) {
    this.objects.push([obj, "qops"]);
    this.dups(obj);
    const keys = new Set(obj.props.map((p) => p.key));
    for (const p of obj.props) {
      if (!p.key.startsWith("$")) continue;
      const op = ops.get(p.key);
      const v = p.value;
      if (op === null) {
        this.unknown(p);
        continue;
      }
      if (op.isA("ejson")) continue;
      if (op.cats.has("qtop") && !op.isA("query", "sub")) {
        this.onProp(p, ERROR, "misplaced-operator", `${p.key} must be at the top level of the query, not inside a field.`);
        continue;
      }
      if (!op.isA("query", "sub", "proj")) {
        this.onProp(p, WARNING, "misplaced-operator", `${p.key} is not a field query operator.`);
        continue;
      }
      const name = p.key;
      if (name === "$in" || name === "$nin" || name === "$all") {
        this.arg(p, new ops.Operator(name, op.cats, "array", op.doc));
      } else if (name === "$not") {
        if (v !== null && v.kind === "object") this.qops(v);
        else if (v !== null && !dynOr("regex").has(v.kind)) {
          this.add(v.start, v.end, ERROR, "bad-argument", "$not expects an operator expression or a regex.");
        }
      } else if (name === "$elemMatch") {
        if (v !== null && v.kind === "object") {
          const inner = v.props.map((q) => q.key);
          if (inner.length && inner.every((k) => ops.OPERATORS.has(k) && ops.OPERATORS.get(k).isA("query", "sub") &&
              !ops.OPERATORS.get(k).cats.has("qtop"))) this.qops(v);
          else this.query(v);
        } else if (v !== null && !dyn(v.kind)) {
          this.add(v.start, v.end, ERROR, "bad-argument", "$elemMatch expects an object.");
        }
      } else if (name === "$regex") {
        if (v !== null && !dynOr("string", "regex").has(v.kind)) {
          this.add(v.start, v.end, ERROR, "bad-argument", "$regex expects a string or regex.");
        }
      } else if (name === "$options") {
        if (!keys.has("$regex")) this.onProp(p, WARNING, "missing-field", "$options has no effect without a $regex sibling.");
        this.arg(p, op);
      } else if (name === "$type") {
        if (v !== null && !dynOr("string", "number", "array").has(v.kind)) {
          this.add(v.start, v.end, ERROR, "bad-argument", "$type expects a type name, number or array.");
        }
      } else if (name === "$near" || name === "$nearSphere" || name === "$geoWithin" || name === "$geoIntersects") {
        if (v !== null && v.kind === "object") this.objects.push([v, "geo"]);
      } else {
        this.arg(p, op);
      }
    }
  }

  // ---- aggregation expressions
  expr(node) {
    if (node.kind === "array") for (const it of node.items) this.expr(it);
    else if (node.kind === "object") this.exprObject(node);
  }

  exprObject(obj) {
    this.objects.push([obj, "expr"]);
    this.dups(obj);
    const dollar = obj.props.filter((p) => p.key.startsWith("$"));
    if (!dollar.length) {
      for (const p of obj.props) if (p.value !== null) this.expr(p.value);
      return;
    }
    if (obj.props.length > 1 && !obj.props.every((p) => ops.get(p.key) && ops.OPERATORS.get(p.key).isA("sub", "ejson"))) {
      this.add(obj.start, obj.start + 1, ERROR, "stage-shape",
        "An expression object must contain exactly one operator key; " +
        `found ${obj.props.length} keys.`);
    }
    for (const p of dollar) {
      const op = ops.get(p.key);
      if (op === null) {
        this.unknown(p, "expression operator");
        continue;
      }
      if (op.cats.has("removed")) {
        this.onProp(p, ERROR, "removed-operator", `${p.key}: ${op.doc}`);
        continue;
      }
      if (op.isA("sub", "ejson")) continue;
      if (!op.isA("expr", "acc", "proj")) {
        this.onProp(p, WARNING, "misplaced-operator", `${p.key} is not an aggregation expression operator.`);
        continue;
      }
      const v = p.value;
      if (p.key === "$literal" || p.key === "$function" || p.key === "$accumulator" || v === null) continue;
      if (p.key === "$cond" && v.kind === "array" && v.items.length !== 3) {
        this.add(v.start, v.end, ERROR, "bad-argument", "$cond array form needs exactly 3 elements [if, then, else].");
      } else if (op.arg === "array2" && v.kind === "array" && v.items.length !== 2) {
        this.add(v.start, v.end, ERROR, "bad-argument", `${p.key} expects exactly 2 arguments.`);
      }
      this.expr(v);
    }
  }

  // ---- projection / $addFields
  fields(obj, { project, label = "fields" }) {
    this.objects.push([obj, label]);
    this.dups(obj);
    const flags = [];
    this.collectProj(obj, flags);
    if (project) {
      const inc = flags.filter(([p, f]) => f && p.key !== "_id");
      const exc = flags.filter(([p, f]) => !f && p.key !== "_id");
      if (inc.length && exc.length) {
        for (const [p] of exc) {
          this.onProp(p, ERROR, "projection-mix",
            "Cannot mix exclusion with inclusion in one projection (only _id may differ).");
        }
      }
    }
  }

  collectProj(obj, flags) {
    for (const p of obj.props) {
      const v = p.value;
      if (p.key.startsWith("$")) {
        this.onProp(p, WARNING, "misplaced-operator",
          `Field names here cannot start with '$' (${p.key}); ` +
          "operators belong inside a field's value.");
        continue;
      }
      if (v === null) continue;
      if (v.kind === "number" || v.kind === "bool") {
        flags.push([p, truthy(v.value)]);
      } else if (v.kind === "object" && !v.props.some((q) => q.key.startsWith("$"))) {
        this.objects.push([v, "fields"]);
        this.collectProj(v, flags);
      } else {
        flags.push([p, true]);
        this.expr(v);
      }
    }
  }

  // ---- $group / $sort
  group(obj) {
    this.objects.push([obj, "group"]);
    this.dups(obj);
    if (!obj.props.some((p) => p.key === "_id")) {
      this.add(obj.start, obj.start + 1, ERROR, "missing-field",
        "$group requires an _id field (use _id: null to aggregate all documents).");
    }
    for (const p of obj.props) {
      const v = p.value;
      if (v === null) continue;
      if (p.key === "_id") {
        this.expr(v);
        continue;
      }
      this.accumulator(p);
    }
  }

  accumulator(p) {
    const v = p.value;
    if (dyn(v.kind)) return;
    if (v.kind !== "object" || v.props.length !== 1 || !v.props[0].key.startsWith("$")) {
      this.onProp(p, ERROR, "stage-shape", `Field ${pyRepr(p.key)} must be an accumulator expression such as { $sum: 1 }.`);
      return;
    }
    this.objects.push([v, "accexpr"]);
    const a = v.props[0];
    const op = ops.get(a.key);
    if (op === null) this.unknown(a, "accumulator");
    else if (!op.isA("acc", "expr")) this.onProp(a, ERROR, "misplaced-operator", `${a.key} is not an accumulator.`);
    else if (a.value !== null && a.key !== "$accumulator") this.expr(a.value);
  }

  sort(obj, { strictStrings }) {
    this.objects.push([obj, "sort"]);
    this.dups(obj);
    for (const p of obj.props) {
      const v = p.value;
      if (v === null || dyn(v.kind)) continue;
      if (v.kind === "number" && (v.value === 1 || v.value === -1)) continue;
      if (v.kind === "object" && v.props.length === 1 && v.props[0].key === "$meta") continue;
      if (v.kind === "string" && !strictStrings && SORT_WORDS.has(v.value)) continue;
      this.add(v.start, v.end, ERROR, "bad-argument", `Sort order for ${pyRepr(p.key)} must be 1, -1 or { $meta: … }.`);
    }
  }

  // ---- update documents
  update(obj, { requireOps = true } = {}) {
    this.objects.push([obj, "update"]);
    this.dups(obj);
    const dollar = obj.props.filter((p) => p.key.startsWith("$"));
    const plain = obj.props.filter((p) => !p.key.startsWith("$"));
    if (dollar.length && plain.length) {
      for (const p of plain) {
        this.onProp(p, ERROR, "update-shape", `${pyRepr(p.key)} mixes a plain field with update operators; wrap it in $set.`);
      }
    } else if (plain.length && requireOps) {
      this.add(obj.start, obj.start + 1, ERROR, "update-shape",
        "Update document requires atomic operators such as $set; " +
        "a plain document is only valid for replaceOne/findOneAndReplace.");
    } else if (!obj.props.length && requireOps) {
      this.add(obj.start, obj.end, ERROR, "update-shape", "Update document is empty; add an operator such as $set.");
    }
    for (const p of dollar) {
      const op = ops.get(p.key);
      const v = p.value;
      if (op === null) {
        this.unknown(p, "update operator");
        continue;
      }
      if (op.cats.has("removed")) {
        this.onProp(p, ERROR, "removed-operator", `${p.key}: ${op.doc}`);
        continue;
      }
      if (!op.cats.has("update")) {
        this.onProp(p, ERROR, "misplaced-operator", `${p.key} is not an update operator.`);
        continue;
      }
      if (v === null) continue;
      if (v.kind !== "object") {
        if (!dyn(v.kind)) this.add(v.start, v.end, ERROR, "bad-argument", `${p.key} expects an object of field: value pairs.`);
        continue;
      }
      this.dups(v);
      for (const f of v.props) this.updateField(p.key, f);
    }
  }

  updateField(opname, f) {
    const v = f.value;
    if (v === null) return;
    if ((opname === "$inc" || opname === "$mul") && !dynOr("number", "object").has(v.kind)) {
      this.add(v.start, v.end, ERROR, "bad-argument", `${opname} requires a numeric value for ${pyRepr(f.key)}.`);
    } else if (opname === "$pop" && !(dyn(v.kind) || (v.kind === "number" && (v.value === 1 || v.value === -1)))) {
      this.add(v.start, v.end, ERROR, "bad-argument", "$pop requires 1 (last) or -1 (first).");
    } else if (opname === "$rename" && !dynOr("string").has(v.kind)) {
      this.add(v.start, v.end, ERROR, "bad-argument", "$rename requires the new field name as a string.");
    } else if ((opname === "$push" || opname === "$addToSet") && v.kind === "object" && v.props.some((q) => q.key.startsWith("$"))) {
      this.objects.push([v, "upmods"]);
      const allowed = opname === "$push" ? new Set(["$each", "$slice", "$sort", "$position"]) : new Set(["$each"]);
      for (const q of v.props) {
        if (!allowed.has(q.key)) {
          this.onProp(q, ERROR, "misplaced-operator", `${q.key} is not a valid modifier for ${opname}.`);
        } else if (q.key === "$each" && q.value !== null && !dynOr("array").has(q.value.kind)) {
          this.add(q.value.start, q.value.end, ERROR, "bad-argument", "$each expects an array.");
        }
      }
      if (!v.props.some((q) => q.key === "$each")) {
        this.onProp(v.props[0], ERROR, "missing-field", `Modifiers on ${opname} require $each.`);
      }
    } else if (opname === "$pull" && v.kind === "object" && v.props.some((q) => q.key.startsWith("$"))) {
      this.qops(v);
    }
  }

  // ---- pipelines
  pipeline(node, { update = false, facet = false } = {}) {
    if (this.done.has(node) && node.kind === "array" && this.arrays.some(([a]) => a === node)) return;
    this.done.add(node);
    if (node.kind === "object") {
      this.add(node.start, node.end, ERROR, "bad-argument", "A pipeline must be an array of stages, not an object.");
      return;
    }
    if (node.kind !== "array") return;
    this.arrays.push([node, "pipeline"]);
    const syms = [];
    const n = node.items.length;
    node.items.forEach((item, i) => {
      if (item.kind !== "object") {
        if (!dyn(item.kind)) this.add(item.start, item.end, ERROR, "stage-shape", "Each pipeline stage must be an object.");
        return;
      }
      const name = this.stage(item, i, i === n - 1, update, facet);
      if (name) syms.push(new Symbol_(name, "stage", item.start, item.end));
    });
    this.stageSyms.set(node, syms);
  }

  stage(obj, idx, last, update, facet, standalone = false) {
    this.objects.push([obj, "pipeline-item"]);
    this.dups(obj);
    if (obj.props.length !== 1) {
      const msg = !obj.props.length ? "Empty stage object." :
        `A stage must have exactly one key; found ${obj.props.length} (split into separate stages).`;
      this.add(obj.start, obj.start + 1, ERROR, "stage-shape", msg);
      return obj.props.length ? obj.props[0].key : null;
    }
    const p = obj.props[0];
    const op = ops.get(p.key);
    if (op === null) {
      this.unknown(p, "stage");
      return p.key;
    }
    if (!op.cats.has("stage")) {
      let hint = "";
      if (op.isA("query", "qtop")) hint = ` Did you mean { $match: { … ${p.key} … } }?`;
      else if (op.isA("expr", "acc")) hint = " Expressions go inside $project, $addFields or $group.";
      this.onProp(p, ERROR, "misplaced-operator", `${p.key} is not an aggregation stage.${hint}`);
      return p.key;
    }
    if (!standalone) {
      if (ops.FIRST_STAGE_ONLY.has(p.key) && idx > 0) this.onProp(p, ERROR, "stage-position", `${p.key} must be the first stage of the pipeline.`);
      if (ops.LAST_STAGE_ONLY.has(p.key) && !last) this.onProp(p, ERROR, "stage-position", `${p.key} must be the last stage of the pipeline.`);
      if (facet && ops.NOT_IN_FACET.has(p.key)) this.onProp(p, ERROR, "stage-position", `${p.key} is not allowed inside $facet.`);
      if (update && !ops.UPDATE_PIPELINE_STAGES.has(p.key)) {
        this.onProp(p, ERROR, "stage-position",
          `${p.key} is not allowed in an update pipeline ` +
          "(use $addFields/$set, $project/$unset, $replaceRoot/$replaceWith).");
      }
    }
    this.stageArg(p, op, idx === 0);
    return p.key;
  }

  /** Report every missing required key on a stage object, anchored at its opening brace. */
  requireKeys(v, stageName, needed) {
    const have = new Set(v.props.map((q) => q.key));
    for (const need of needed) {
      if (!have.has(need)) this.add(v.start, v.start + 1, ERROR, "missing-field", `${stageName} requires ${need}.`);
    }
    return have;
  }

  accumulatorOutputs(q) {
    this.objects.push([q.value, "group"]);
    for (const o of q.value.props) if (o.value !== null) this.accumulator(o);
  }

  stageArg(p, op, first) {
    const v = p.value;
    const name = p.key;
    if (v === null) return;
    if (!FREE_FORM.has(name) && !this.arg(p, op)) return;
    if (name === "$match") {
      if (v.kind === "object") {
        this.query(v, { inMatch: true, first });
        for (const q of v.props) {
          if (q.key === "$near" || q.key === "$nearSphere") {
            this.onProp(q, ERROR, "misplaced-operator", `${q.key} is not allowed in $match; use $geoNear.`);
          }
        }
      }
    } else if (name === "$project") {
      if (v.kind === "object") this.fields(v, { project: true });
    } else if (name === "$addFields" || name === "$set") {
      if (v.kind === "object") this.fields(v, { project: false });
    } else if (name === "$group") {
      if (v.kind === "object") this.group(v);
    } else if (name === "$sort") {
      if (v.kind === "object") this.sort(v, { strictStrings: true });
    } else if (name === "$unwind") {
      if (v.kind === "string" && !String(v.value).startsWith("$")) {
        this.add(v.start, v.end, ERROR, "bad-argument", '$unwind path must start with \'$\' (e.g. "$items").');
      } else if (v.kind === "object") {
        this.objects.push([v, "stage"]);
        const path = v.props.find((q) => q.key === "path") ?? null;
        if (path === null) {
          this.add(v.start, v.start + 1, ERROR, "missing-field", "$unwind requires a path.");
        } else if (path.value !== null && path.value.kind === "string" && !String(path.value.value).startsWith("$")) {
          this.add(path.value.start, path.value.end, ERROR, "bad-argument", "$unwind path must start with '$'.");
        }
      } else if (!dynOr("string").has(v.kind)) {
        this.add(v.start, v.end, ERROR, "bad-argument", "$unwind expects a path string or an object.");
      }
    } else if (name === "$lookup") {
      if (v.kind === "object") this.lookup(v);
    } else if (name === "$facet") {
      if (v.kind === "object") {
        this.objects.push([v, "stage"]);
        for (const q of v.props) if (q.value !== null) this.pipeline(q.value, { facet: true });
      }
    } else if (name === "$unionWith") {
      if (v.kind === "object") {
        this.objects.push([v, "stage"]);
        for (const q of v.props) if (q.key === "pipeline" && q.value !== null) this.pipeline(q.value);
      }
    } else if (name === "$replaceRoot" || name === "$replaceWith") {
      if (name === "$replaceRoot" && v.kind === "object") {
        this.objects.push([v, "stage"]);
        const nr = v.props.find((q) => q.key === "newRoot") ?? null;
        if (nr === null) this.add(v.start, v.start + 1, ERROR, "missing-field", "$replaceRoot requires newRoot.");
        else if (nr.value !== null) this.expr(nr.value);
      } else if (name === "$replaceWith") {
        this.expr(v);
      }
    } else if (name === "$sortByCount" || name === "$redact") {
      this.expr(v);
    } else if (name === "$unset") {
      if (!dynOr("string", "array").has(v.kind)) {
        this.add(v.start, v.end, ERROR, "bad-argument", "$unset expects a field name or an array of names.");
      }
    } else if (name === "$graphLookup" && v.kind === "object") {
      this.objects.push([v, "stage"]);
      this.requireKeys(v, "$graphLookup", ["from", "startWith", "connectFromField", "connectToField", "as"]);
      for (const q of v.props) {
        if (q.key === "startWith" && q.value !== null) this.expr(q.value);
        else if (q.key === "restrictSearchWithMatch" && q.value !== null && q.value.kind === "object") this.query(q.value);
      }
    } else if (name === "$geoNear" && v.kind === "object") {
      this.objects.push([v, "stage"]);
      this.requireKeys(v, "$geoNear", ["near", "distanceField"]);
      for (const q of v.props) {
        if (q.key === "query" && q.value !== null && q.value.kind === "object") this.query(q.value);
      }
    } else if (name === "$vectorSearch" && v.kind === "object") {
      this.objects.push([v, "stage"]);
      const have = this.requireKeys(v, "$vectorSearch", ["index", "path", "limit"]);
      if (!have.has("queryVector") && !have.has("query")) {
        this.add(v.start, v.start + 1, ERROR, "missing-field", "$vectorSearch requires queryVector (or query for auto-embedding).");
      }
      const exact = v.props.find((q) => q.key === "exact") ?? null;
      if (!have.has("numCandidates") && !(exact !== null && exact.value !== null && exact.value.value === true)) {
        this.add(v.start, v.start + 1, WARNING, "missing-field",
          "ANN $vectorSearch needs numCandidates (or set exact: true).");
      }
    } else if (name === "$setWindowFields" && v.kind === "object") {
      this.objects.push([v, "stage"]);
      for (const q of v.props) {
        if (q.key === "output" && q.value !== null && q.value.kind === "object") this.accumulatorOutputs(q);
      }
    } else if ((name === "$bucket" || name === "$bucketAuto") && v.kind === "object") {
      this.objects.push([v, "stage"]);
      for (const q of v.props) {
        if (q.key === "groupBy" && q.value !== null) this.expr(q.value);
        else if (q.key === "output" && q.value !== null && q.value.kind === "object") this.accumulatorOutputs(q);
      }
    } else if (v.kind === "object" && ["$sample", "$merge", "$out", "$search", "$searchMeta", "$fill", "$densify"].includes(name)) {
      this.objects.push([v, "stage"]);
      if (name === "$sample" && !v.props.some((q) => q.key === "size")) {
        this.add(v.start, v.start + 1, ERROR, "missing-field", "$sample requires size.");
      }
    }
  }

  lookup(obj) {
    this.objects.push([obj, "lookup"]);
    this.dups(obj);
    const keys = new Map();
    for (const p of obj.props) keys.set(p.key, p);
    for (const p of obj.props) {
      if (!["from", "localField", "foreignField", "as", "let", "pipeline"].includes(p.key)) {
        this.onProp(p, WARNING, "unknown-field", `${pyRepr(p.key)} is not a $lookup option.`);
      }
    }
    if (!keys.has("as")) this.add(obj.start, obj.start + 1, ERROR, "missing-field", "$lookup requires as.");
    const hasPipe = keys.has("pipeline");
    if (!hasPipe) {
      for (const need of ["localField", "foreignField"]) {
        if (!keys.has(need)) this.add(obj.start, obj.start + 1, ERROR, "missing-field", `$lookup without a pipeline requires ${need}.`);
      }
    }
    if (!keys.has("from") && !hasPipe) this.add(obj.start, obj.start + 1, ERROR, "missing-field", "$lookup requires from.");
    if (hasPipe && keys.get("pipeline").value !== null) this.pipeline(keys.get("pipeline").value);
    if (keys.has("let") && keys.get("let").value !== null && keys.get("let").value.kind === "object") {
      for (const q of keys.get("let").value.props) if (q.value !== null) this.expr(q.value);
    }
  }

  // ---- symbols
  symbols() {
    const out = [];
    for (const st of this.statements) {
      const kind = st.decl ? "variable" : "method";
      const label = st.decl ? st.decl : chainName(st.node);
      if (label === null) continue;
      const kids = [];
      for (const n of st.node.walk()) {
        if (n.kind === "array" && this.stageSyms.has(n) && !kids.some((k) => k.start <= n.start && n.end <= k.end)) {
          kids.push(...this.stageSyms.get(n));
        }
      }
      out.push(new Symbol_(label, kind, st.start, st.end, kids));
    }
    return out;
  }
}

/** Dotted name of the outermost db.coll.method(...) call in a chain. */
function chainName(node) {
  let n = node;
  let lastCall = null;
  while (n !== null) {
    if (n.kind === "call") {
      lastCall = n;
      n = n.target;
    } else if (n.kind === "member") {
      n = n.target;
    } else break;
  }
  let target = lastCall ? lastCall.target : null;
  let first = null;
  n = node;
  while (n !== null) {
    if (n.kind === "call") {
      if (n.target !== null && n.target.kind === "member") first = n;
      n = n.target;
    } else if (n.kind === "member") {
      n = n.target;
    } else break;
  }
  if (first) target = first.target;
  if (target === null) return null;
  const parts = [];
  while (target !== null && target.kind === "member") {
    parts.push(String(target.value));
    target = target.target;
  }
  if (target !== null && target.kind === "ident") parts.push(String(target.value));
  return parts.reverse().join(".") || null;
}

/** Analyze MQL text. Returns { text, statements, diagnostics, objects, arrays, symbols }. */
export function analyze(text) {
  return new Analyzer(text).run();
}

/** Diagnostics in the golden/wire shape: adds 0-based line and UTF-16 column of `start`. */
export function diagnosticsToDicts(text, diagnostics) {
  return diagnostics.map((d) => {
    const { line, column } = offsetToPosition(text, d.start);
    return { start: d.start, end: d.end, line, column, severity: d.severity, code: d.code, message: d.message, fix: d.fix };
  });
}

/** Nested symbol outline as plain dicts (name/kind/start/end/children). */
export function symbolsToDicts(symbols) {
  return symbols.map((s) => ({ name: s.name, kind: s.kind, start: s.start, end: s.end, children: symbolsToDicts(s.children) }));
}

/** The comparable summary of an analysis: diagnostics and symbol outline. */
export function toDict(text, result = analyze(text)) {
  return { diagnostics: diagnosticsToDicts(text, result.diagnostics), symbols: symbolsToDicts(result.symbols) };
}
