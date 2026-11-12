// report — the Markdown case note the popup copies to the clipboard.
import { docFor, ESR_DOC } from "./docs.js";
import { SEVERITY_ORDER } from "./optimize.js";

const KIND_LABEL = { mongosh: "mongosh query", log: "slow-query log line", profile: "profiler entry",
  command: "command document", filter: "bare filter (collection name unknown)",
  pipeline: "bare pipeline (collection name unknown)" };

export function kindLabel(kind) {
  return Object.hasOwn(KIND_LABEL, kind) ? KIND_LABEL[kind] : kind;
}

/** Severity counts in display order, e.g. [["blocking", 1], ["high", 2]] (zero counts dropped). */
export function severityCounts(rep) {
  return Object.keys(SEVERITY_ORDER)
    .map((s) => [s, rep.findings.filter((f) => f.severity === s && !f.code.endsWith("-rewrite")).length])
    .filter(([, n]) => n);
}

/** docsExamined / nreturned as "92,161:1", or null when the log did not carry both. */
export function scanRatio(ev) {
  if (!Number.isFinite(ev.docsExamined) || !Number.isFinite(ev.nreturned) || ev.docsExamined < 0 || ev.nreturned < 0) return null;
  return `${Math.round(ev.docsExamined / Math.max(ev.nreturned, 1)).toLocaleString("en-US")}:1`;
}

function fence(code, lang = "js") {
  const text = String(code).trimEnd();
  const size = [...text.matchAll(/`+/g)].reduce((size, m) => Math.max(size, m[0].length + 1), 3);
  const ticks = "`".repeat(size);
  return ticks + lang + "\n" + text + "\n" + ticks;
}

// Flatten line breaks so input cannot create paragraphs, headings or list items in case notes.
function literal(value) {
  return String(value).replace(/\s+/gu, " ").replace(/[\\`*_{}\[\]()<>#+.!|~-]/g, "\\$&");
}

function inlineCode(value) {
  const text = String(value).replace(/\s+/gu, " ");
  // Backticks and whitespace require a delimiter longer than the value and padding per CommonMark.
  if (!text.includes("`")) return "`" + text + "`";
  const ticks = "`".repeat([...text.matchAll(/`+/g)].reduce((size, m) => Math.max(size, m[0].length + 1), 1));
  return ticks + " " + text + " " + ticks;
}

/** Case comment Markdown. Interpreted input and rewrites can include sensitive literals; review before pasting. */
export function toMarkdown(rep) {
  const L = [];
  const counts = severityCounts(rep).map(([s, n]) => `${n} ${s}`).join(", ") || "no open findings";
  L.push(`**MQL optimizer (static review)** — ${rep.inputQueries} quer${rep.inputQueries === 1 ? "y" : "ies"}, ${counts}` +
    (rep.applied.length ? `, ${rep.applied.length} safe rewrite(s)` : ""));
  L.push("");
  if (rep.interpreted !== null) {
    L.push(`Input: ${Object.hasOwn(KIND_LABEL, rep.inputKind) ? kindLabel(rep.inputKind) : literal(rep.inputKind)}, read as:`);
    L.push(fence(rep.interpreted));
  }
  rep.evidence.forEach((ev, i) => {
    if (!Object.keys(ev).length) return;
    const bits = [];
    if (ev.planSummary !== undefined) bits.push(`plan ${inlineCode(ev.planSummary)}`);
    if (ev.durationMillis !== undefined) bits.push(`${literal(ev.durationMillis)} ms`);
    if (ev.docsExamined !== undefined) bits.push(`docsExamined ${literal(ev.docsExamined)}`);
    if (ev.keysExamined !== undefined) bits.push(`keysExamined ${literal(ev.keysExamined)}`);
    if (ev.nreturned !== undefined) bits.push(`nreturned ${literal(ev.nreturned)}`);
    const r = scanRatio(ev);
    if (r) bits.push(`scan ratio ${r}`);
    L.push(`Logged evidence${rep.evidence.length > 1 ? ` (query ${i + 1})` : ""}: ${bits.join(", ")}`);
  });
  const findings = rep.findings.filter((f) => !f.code.endsWith("-rewrite"));
  if (findings.length) {
    L.push("", "**Findings**");
    for (const f of findings) {
      const doc = docFor(f.code);
      L.push(`- **${literal(f.severity.toUpperCase())}** ${inlineCode(f.code)} (${literal(f.pass)}): ${literal(f.message)}${doc ? ` [MongoDB docs](${doc})` : ""}`);
    }
  }
  if (rep.applied.length) {
    L.push("", "**Safe rewrites (same results)**");
    for (const f of rep.applied) L.push(`- ${inlineCode(f.code)}: ${literal(f.message.split(". ")[0].replace(/\.+$/, ""))}.`);
    L.push("", "Rewritten:", fence(rep.text));
  }
  if (rep.indexes.length) {
    L.push("", `**Index recommendations** (test on non-production first; check existing indexes) — [ESR guideline](${ESR_DOC})`);
    for (const r of rep.indexes) L.push(fence(r.shell()), `_${literal(r.rationale)}_`);
  }
  L.push("", "_Static analysis only. Confirm with `explain(\"executionStats\")`: COLLSCAN → IXSCAN, " +
    "totalDocsExamined / nReturned near 1, nReturned unchanged._");
  return L.join("\n");
}
