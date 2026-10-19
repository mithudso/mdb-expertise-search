// ui — DOM helpers shared by the popup and the app page. Text from pages and the corpus is always inserted
// as text nodes (never parsed as HTML).
import { docFor, ESR_DOC } from "./docs.js";
import { kindLabel, scanRatio, severityCounts, toMarkdown } from "./report.js";
import { STOPWORDS } from "./textsearch.js";

// question words that are not in the search stopword list but make poor highlights
const EXTRA_STOP = new Set(["used", "use", "using", "get", "getting", "should", "would", "could", "there", "they"]);

/** Build an element. Children are nodes or strings (strings become text nodes). */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export async function copyText(text, btn) {
  const label = btn.textContent;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copied";
  } catch {
    btn.textContent = "Copy failed";
  }
  setTimeout(() => { btn.textContent = label; }, 1500);
}

export function copyButton(getText, label = "Copy") {
  const b = h("button", { type: "button", class: "small" }, label);
  b.addEventListener("click", () => copyText(getText(), b));
  return b;
}

export function externalLink(href, text) {
  return h("a", { href, target: "_blank", rel: "noopener noreferrer" }, text);
}

// ---- optimizer report

/**
 * Render an optimizer report. `refLink(ref)` returns an element linking to the corpus page behind a finding
 * (or null); `extra` is appended to the action row.
 */
export function renderReport(rep, { refLink = () => null, extra = [] } = {}) {
  const root = h("div", { class: "report" });
  const counts = severityCounts(rep);
  const findings = rep.findings.filter((f) => !f.code.endsWith("-rewrite"));
  if (!rep.inputQueries) {
    root.append(h("p", { class: "status error" },
      "No query found. Highlight or paste a mongosh query (db.coll.find(…), aggregate([…])), a slow-query log line, " +
      "a profiler entry, a { find: … } command, a filter or a pipeline."));
    return root;
  }
  root.append(h("div", { class: "summary" },
    h("strong", {}, `${rep.inputQueries} quer${rep.inputQueries === 1 ? "y" : "ies"}`),
    counts.length ? counts.map(([s, n]) => h("span", { class: `chip sev-${s}` }, `${n} ${s}`))
      : h("span", { class: "chip ok" }, "no open findings"),
    rep.applied.length ? h("span", { class: "chip ok" }, `${rep.applied.length} safe rewrite${rep.applied.length > 1 ? "s" : ""}`) : null,
    h("span", { class: "kind" }, `· ${kindLabel(rep.inputKind)}`)));
  root.append(h("div", { class: "row" },
    copyButton(() => toMarkdown(rep), "Copy as Markdown for the case"),
    rep.changed ? copyButton(() => rep.text, "Copy rewritten query") : null, extra));
  if (rep.interpreted !== null) {
    root.append(h("h2", {}, `Read the ${kindLabel(rep.inputKind)} as`), h("pre", {}, rep.interpreted.trimEnd()));
  }
  rep.evidence.forEach((ev, i) => {
    if (!Object.keys(ev).length) return;
    const metric = (value, label) => (value === undefined || value === null ? null :
      h("div", { class: "metric" }, h("b", {}, String(value)), h("span", {}, label)));
    root.append(h("h2", {}, rep.evidence.length > 1 ? `Logged evidence — query ${i + 1}` : "Logged evidence"),
      h("div", { class: "evidence" },
        metric(ev.planSummary, "plan"),
        metric(ev.durationMillis !== undefined ? `${ev.durationMillis} ms` : undefined, "duration"),
        metric(ev.docsExamined, "docsExamined"), metric(ev.keysExamined, "keysExamined"),
        metric(ev.nreturned, "nreturned"), metric(scanRatio(ev), "scanned : returned")));
  });
  if (findings.length) {
    root.append(h("h2", {}, "Findings"), ...findings.map((f) => {
      const doc = docFor(f.code);
      return h("div", { class: `finding sev-${f.severity}` },
        h("div", { class: "head" }, h("span", {}, f.severity.toUpperCase()), h("span", { class: "kind" }, `${f.pass} · ${f.code}`)),
        h("p", {}, f.message),
        h("div", { class: "links" }, doc ? externalLink(doc, "MongoDB docs") : null, f.ref ? refLink(f.ref) : null));
    }));
  }
  if (rep.applied.length) {
    root.append(h("h2", {}, "Safe rewrites applied (same results)"),
      h("ul", { class: "applied" }, rep.applied.map((f) => h("li", {}, `${f.message.split(". ")[0].replace(/\.+$/, "")}.`))),
      h("pre", {}, rep.text.trimEnd()));
  }
  if (rep.indexes.length) {
    root.append(h("h2", {}, "Index recommendations"),
      h("p", { class: "kind" }, "Recommend-only: check existing indexes and build on non-production first. ",
        externalLink(ESR_DOC, "ESR guideline")),
      ...rep.indexes.map((r) => h("div", { class: "index" },
        h("div", { class: "line" }, h("pre", {}, r.shell()), copyButton(() => r.shell())),
        h("p", {}, r.rationale))));
  }
  return root;
}

// ---- minimal, safe markdown for corpus pages

const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\((https?:\/\/[^)\s]+)\))/g;

function inline(text, mark) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(...marked(text.slice(last, m.index), mark));
    const tok = m[0];
    if (tok.startsWith("`")) out.push(h("code", {}, tok.slice(1, -1)));
    else if (tok.startsWith("**")) out.push(h("strong", {}, ...marked(tok.slice(2, -2), mark)));
    else out.push(externalLink(m[2], tok.slice(1, tok.indexOf("]("))));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(...marked(text.slice(last), mark));
  return out;
}

function marked(text, mark) {
  if (!mark) return [text];
  const out = [];
  let last = 0;
  for (const m of text.matchAll(mark)) {
    if (!m[0]) break;
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(h("mark", {}, m[0]));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Render markdown-ish corpus text (headings, fences, lists, tables as text, inline code/bold/links). */
export function renderMarkdown(text, { mark = null } = {}) {
  const frag = document.createDocumentFragment();
  const lines = text.split("\n");
  let i = 0;
  let list = null;
  let para = [];
  const flushPara = () => {
    if (para.length) frag.append(h("p", {}, inline(para.join(" "), mark)));
    para = [];
  };
  const flushList = () => {
    if (list) frag.append(list);
    list = null;
  };
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {
      flushPara(); flushList();
      const code = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i++]);
      i++;
      frag.append(h("pre", {}, code.join("\n")));
      continue;
    }
    const hm = /^(#{1,6})\s+(.*)$/.exec(line);
    if (hm) {
      flushPara(); flushList();
      frag.append(h(`h${Math.min(6, hm[1].length + 2)}`, {}, inline(hm[2], mark)));
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      flushPara();
      if (!list) list = h(/^\s*\d+\./.test(line) ? "ol" : "ul", {});
      list.append(h("li", {}, inline(line.replace(/^\s*([-*]|\d+\.)\s+/, ""), mark)));
    } else if (/^\s*\|/.test(line)) {
      flushPara(); flushList();
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      frag.append(h("pre", { class: "table" }, rows.join("\n")));
      continue;
    } else if (!line.trim()) {
      flushPara(); flushList();
    } else {
      flushList();
      para.push(line.trim());
    }
    i++;
  }
  flushPara(); flushList();
  return frag;
}

/** A regex that marks the search words of `query` (stopwords skipped, loose stemming by prefix), or null. */
export function markFor(query) {
  const words = (String(query).match(/[\p{L}\p{N}_$]{2,}/gu) || []).map((w) => w.replace(/^\$/, ""))
    .filter((w) => w.length > 2 && !STOPWORDS.has(w.toLowerCase()) && !EXTRA_STOP.has(w.toLowerCase()))
    .map((w) => w.slice(0, Math.max(3, w.length - 2)).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return words.length ? new RegExp(`\\b(?:${words.join("|")})\\w*`, "giu") : null;
}
