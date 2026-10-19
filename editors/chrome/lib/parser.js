// parser — a tolerant parser for mongosh-style MQL. JavaScript port of mdbx/mql/parser.py.
//
// Accepts relaxed JSON / JavaScript object literals plus the call shapes that appear in mongosh
// scripts: db.coll.find({...}).sort({...}), ObjectId("..."), ISODate(...), regex literals,
// `const x = [...]`. It never throws: syntax problems become error records and the parser
// resynchronises. All positions are 0-based UTF-16 offsets into the source text.
//
// Keep in step with the Python reference: tests/fixtures/optimizer/*.golden.json pins the output.

const IDENT = /[A-Za-z_$][\w$]*/y;
const NUMBER = /[-+]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|Infinity|NaN)/y;
const PROP_NUM = /-?\d+(?:\.\d+)?/y;
const DECL_REST = /\s+([A-Za-z_$][\w$]*)\s*=/y;
const USE_REST = /[ \t]+[\w$-]+[ \t]*(?=\n|;|$)/y;
const FLAGS = /[a-z]*/y;
const KEYWORDS = { true: "bool", false: "bool", null: "null", undefined: "undefined" };
const DECL = new Set(["const", "let", "var"]);

function matchAt(re, s, i) {
  re.lastIndex = i;
  const m = re.exec(s);
  return m;
}

export class Node {
  constructor(kind, start, end, value = null) {
    this.kind = kind; // object array string number bool null undefined regex ident call member error
    this.start = start;
    this.end = end;
    this.value = value;
    this.props = [];
    this.items = [];
    this.target = null;
    this.nameStart = 0;
    this.closed = true;
  }

  /** Every node in this subtree, in the same order as the Python Node.walk(). */
  walk(out = []) {
    out.push(this);
    for (const p of this.props) if (p.value !== null) p.value.walk(out);
    for (const i of this.items) i.walk(out);
    if (this.target !== null) this.target.walk(out);
    return out;
  }
}

export class Prop {
  constructor(key, keyStart, keyEnd, quoted, value, start, end) {
    Object.assign(this, { key, keyStart, keyEnd, quoted, value, start, end });
  }
}

export class Statement {
  constructor(node, start, end, decl = null) {
    Object.assign(this, { node, start, end, decl });
  }
}

const hex = (n, w) => n.toString(16).padStart(w, "0");

/** Python repr(str): quote choice, escapes and non-printable handling. */
export function pyRepr(s) {
  const q = s.includes("'") && !s.includes('"') ? '"' : "'";
  let out = q;
  for (const ch of s) {
    const cp = ch.codePointAt(0);
    if (ch === q || ch === "\\") out += "\\" + ch;
    else if (ch === "\t") out += "\\t";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (cp < 0x20 || cp === 0x7f) out += "\\x" + hex(cp, 2);
    else if (cp < 0x7f) out += ch;
    else if (!/[\p{C}\p{Z}]/u.test(ch)) out += ch;
    else if (cp <= 0xff) out += "\\x" + hex(cp, 2);
    else if (cp <= 0xffff) out += "\\u" + hex(cp, 4);
    else out += "\\U" + hex(cp, 8);
  }
  return out + q;
}

const isSpace = (c) => /\s/.test(c);

class Parser {
  constructor(text) {
    this.s = text;
    this.n = text.length;
    this.i = 0;
    this.errors = [];
  }

  ws() {
    const s = this.s, n = this.n;
    while (this.i < n) {
      const c = s[this.i];
      if (isSpace(c)) {
        this.i += 1;
      } else if (s.startsWith("//", this.i)) {
        const j = s.indexOf("\n", this.i);
        this.i = j < 0 ? n : j;
      } else if (s.startsWith("/*", this.i)) {
        const j = s.indexOf("*/", this.i + 2);
        if (j < 0) {
          this.err(this.i, n, "unterminated comment");
          this.i = n;
        } else {
          this.i = j + 2;
        }
      } else {
        break;
      }
    }
  }

  err(start, end, msg) {
    this.errors.push({ start, end: Math.max(end, start + 1), message: msg });
  }

  parse() {
    const out = [];
    for (;;) {
      this.ws();
      while (this.i < this.n && this.s[this.i] === ";") {
        this.i += 1;
        this.ws();
      }
      if (this.i >= this.n) break;
      const start = this.i;
      const stmt = this.statement();
      if (stmt !== null) out.push(stmt);
      if (this.i === start) {
        this.err(this.i, this.i + 1, `unexpected ${pyRepr(this.s[this.i])}`);
        this.i += 1;
      }
    }
    return out;
  }

  statement() {
    const start = this.i;
    const m = matchAt(IDENT, this.s, this.i);
    let decl = null;
    if (m && DECL.has(m[0])) {
      const m2 = matchAt(DECL_REST, this.s, this.i + m[0].length);
      if (m2) {
        decl = m2[1];
        this.i = m2.index + m2[0].length;
      }
    } else if (m && m[0] === "use") {
      const m2 = matchAt(USE_REST, this.s, this.i + m[0].length);
      if (m2) {
        this.i = m2.index + m2[0].length;
        return null;
      }
    }
    const node = this.expression();
    if (node === null) {
      this.resync();
      return null;
    }
    this.ws();
    return new Statement(node, start, node.end, decl);
  }

  resync() {
    const j = this.s.indexOf("\n", this.i);
    this.i = j < 0 ? this.n : j + 1;
  }

  expression() {
    let node = this.primary();
    if (node === null) return null;
    for (;;) {
      this.ws();
      if (this.i >= this.n) break;
      const c = this.s[this.i];
      if (c === ".") {
        this.i += 1;
        this.ws();
        const m = matchAt(IDENT, this.s, this.i);
        if (!m) {
          this.err(this.i, this.i + 1, "expected property name after '.'");
          break;
        }
        const end = m.index + m[0].length;
        const mem = new Node("member", node.start, end, m[0]);
        mem.target = node;
        mem.nameStart = m.index;
        node = mem;
        this.i = end;
      } else if (c === "(") {
        node = this.call(node);
      } else if (c === "[" && (node.kind === "ident" || node.kind === "member")) {
        this.i += 1;
        const inner = this.expression();
        this.ws();
        if (this.i < this.n && this.s[this.i] === "]") this.i += 1;
        else this.err(this.i, this.i + 1, "expected ']'");
        const name = inner !== null && inner.kind === "string" ? inner.value : "?";
        const mem = new Node("member", node.start, this.i, name);
        mem.target = node;
        mem.nameStart = node.end;
        node = mem;
      } else {
        break;
      }
    }
    return node;
  }

  call(callee) {
    const openAt = this.i;
    this.i += 1;
    const args = [];
    let closed = false;
    for (;;) {
      this.ws();
      if (this.i >= this.n) {
        this.err(openAt, openAt + 1, "unclosed '('");
        break;
      }
      const c = this.s[this.i];
      if (c === ")") {
        this.i += 1;
        closed = true;
        break;
      }
      if (c === ",") {
        this.i += 1;
        continue;
      }
      const before = this.i;
      const arg = this.expression();
      if (arg === null) this.skipBadValue(new Set([")"]));
      else args.push(arg);
      if (this.i === before) this.i += 1;
    }
    const node = new Node("call", callee.start, this.i);
    node.target = callee;
    node.items = args;
    node.closed = closed;
    return node;
  }

  skipBadValue(closers) {
    let depth = 0;
    const start = this.i;
    while (this.i < this.n) {
      const c = this.s[this.i];
      if ("{[(".includes(c)) {
        depth += 1;
      } else if ("}])".includes(c)) {
        if (depth === 0 && closers.has(c)) break;
        depth = Math.max(depth - 1, 0);
      } else if (c === "," && depth === 0) {
        break;
      }
      this.i += 1;
    }
    if (this.i > start) this.err(start, this.i, "unexpected tokens");
  }

  primary() {
    this.ws();
    if (this.i >= this.n) return null;
    const c = this.s[this.i];
    if (c === "{") return this.object();
    if (c === "[") return this.array();
    if (c === '"' || c === "'" || c === "`") return this.string();
    if (c === "/" && !this.s.startsWith("//", this.i) && !this.s.startsWith("/*", this.i)) return this.regex();
    let m = matchAt(NUMBER, this.s, this.i);
    if (m && ("+-.0123456789".includes(m[0][0]) || m[0] === "Infinity" || m[0] === "NaN")) {
      const text = m[0];
      this.i = m.index + text.length;
      const val = Number(/^[-+]?0[xX]/.test(text) ? (text[0] === "-" ? -Number(text.slice(1)) : Number(text.replace(/^\+/, ""))) : text);
      return new Node("number", m.index, this.i, Number.isNaN(val) && text !== "NaN" ? text : val);
    }
    m = matchAt(IDENT, this.s, this.i);
    if (m) {
      const word = m[0];
      this.i = m.index + word.length;
      if (Object.prototype.hasOwnProperty.call(KEYWORDS, word)) {
        const kind = KEYWORDS[word];
        return new Node(kind, m.index, this.i, kind === "bool" ? word === "true" : null);
      }
      if (word === "new") return this.primary();
      return new Node("ident", m.index, this.i, word);
    }
    return null;
  }

  string() {
    const q = this.s[this.i];
    const start = this.i;
    this.i += 1;
    let buf = "";
    while (this.i < this.n) {
      const c = this.s[this.i];
      if (c === "\\" && this.i + 1 < this.n) {
        const nxt = this.s[this.i + 1];
        buf += { n: "\n", t: "\t", r: "\r" }[nxt] ?? nxt;
        this.i += 2;
        continue;
      }
      if (c === q) {
        this.i += 1;
        return new Node("string", start, this.i, buf);
      }
      if (c === "\n" && q !== "`") break;
      buf += c;
      this.i += 1;
    }
    this.err(start, this.i, "unterminated string");
    const node = new Node("string", start, this.i, buf);
    node.closed = false;
    return node;
  }

  regex() {
    const start = this.i;
    let j = this.i + 1;
    let inClass = false;
    while (j < this.n) {
      const c = this.s[j];
      if (c === "\\") {
        j += 2;
        continue;
      }
      if (c === "[") inClass = true;
      else if (c === "]") inClass = false;
      else if (c === "/" && !inClass) break;
      else if (c === "\n") {
        j = this.n;
        break;
      }
      j += 1;
    }
    if (j >= this.n) {
      this.err(start, Math.min(this.n, start + 1), "unterminated regular expression");
      this.i = Math.min(this.n, start + 1);
      return new Node("error", start, this.i);
    }
    const src = this.s.slice(start + 1, j);
    j += 1;
    const m = matchAt(FLAGS, this.s, j);
    const flags = m ? m[0] : "";
    this.i = j + flags.length;
    return new Node("regex", start, this.i, src + "/" + flags);
  }

  array() {
    const start = this.i;
    this.i += 1;
    const items = [];
    let closed = false;
    for (;;) {
      this.ws();
      if (this.i >= this.n) {
        this.err(start, start + 1, "unclosed '['");
        break;
      }
      const c = this.s[this.i];
      if (c === "]") {
        this.i += 1;
        closed = true;
        break;
      }
      if (c === ",") {
        this.i += 1;
        continue;
      }
      if (c === "}" || c === ")") {
        this.err(this.i, this.i + 1, `unexpected '${c}'; expected ']'`);
        break;
      }
      const before = this.i;
      const val = this.expression();
      if (val === null) this.skipBadValue(new Set(["]"]));
      else items.push(val);
      if (this.i === before) this.i += 1;
    }
    const node = new Node("array", start, this.i);
    node.items = items;
    node.closed = closed;
    return node;
  }

  object() {
    const start = this.i;
    this.i += 1;
    const props = [];
    let closed = false;
    for (;;) {
      this.ws();
      if (this.i >= this.n) {
        this.err(start, start + 1, "unclosed '{'");
        break;
      }
      const c = this.s[this.i];
      if (c === "}") {
        this.i += 1;
        closed = true;
        break;
      }
      if (c === ",") {
        this.i += 1;
        continue;
      }
      if (c === "]" || c === ")") {
        this.err(this.i, this.i + 1, `unexpected '${c}'; expected '}'`);
        break;
      }
      const before = this.i;
      const prop = this.prop();
      if (prop !== null) props.push(prop);
      if (this.i === before) this.i += 1;
    }
    const node = new Node("object", start, this.i);
    node.props = props;
    node.closed = closed;
    return node;
  }

  prop() {
    this.ws();
    const k0 = this.i;
    const c = this.s[this.i];
    const quoted = c === '"' || c === "'";
    let key;
    if (quoted) {
      key = String(this.string().value);
    } else {
      const m = matchAt(IDENT, this.s, this.i) || matchAt(PROP_NUM, this.s, this.i);
      if (!m) {
        this.err(this.i, this.i + 1, "expected a property name");
        this.skipBadValue(new Set(["}"]));
        return null;
      }
      key = m[0];
      this.i = m.index + m[0].length;
    }
    const k1 = this.i;
    this.ws();
    if (this.i < this.n && this.s[this.i] === ":") {
      this.i += 1;
    } else if (this.i < this.n && (this.s[this.i] === "," || this.s[this.i] === "}")) {
      this.err(k0, k1, `property ${pyRepr(key)} has no value`);
      return new Prop(key, k0, k1, quoted, null, k0, k1);
    } else {
      this.err(this.i, this.i + 1, "expected ':'");
      this.skipBadValue(new Set(["}"]));
      return new Prop(key, k0, k1, quoted, null, k0, this.i);
    }
    const val = this.expression();
    if (val === null) {
      this.err(this.i, this.i + 1, `expected a value for ${pyRepr(key)}`);
      this.skipBadValue(new Set(["}"]));
    }
    return new Prop(key, k0, k1, quoted, val, k0, val ? val.end : this.i);
  }
}

/** Parse text into statements; never throws. Returns [statements, errors]. */
export function parse(text) {
  const p = new Parser(text);
  const stmts = p.parse();
  return [stmts, p.errors];
}
