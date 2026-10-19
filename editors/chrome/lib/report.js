// report — the Markdown case note the popup copies to the clipboard.
import { docFor, ESR_DOC } from "./docs.js";
import { SEVERITY_ORDER } from "./optimize.js";

const KIND_LABEL = { mongosh: "mongosh query", log: "slow-query log line", profile: "profiler entry",
  command: "command document", filter: "bare filter (collection name unknown)",
  pipeline: "bare pipeline (collection name unknown)" };

export function kindLabel(kind) {
  return KIND_LABEL[kind] ?? kind;
}

/** Severity counts in display order, e.g. [["blocking", 1], ["high", 2]] (zero counts dropped). */
export function severityCounts(rep) {
  return Object.keys(SEVERITY_ORDER)
    .map((s) => [s, rep.findings.filter((f) => f.severity === s && !f.code.endsWith("-rewrite")).length])
    .filter(([, n]) => n);
}

/** docsExamined / nreturned as "92,161:1", or null when the log did not carry both. */
export function scanRatio(ev) {
  if (typeof ev.docsExamined !== "number" || typeof ev.nreturned !== "number") return null;
  return `${Math.round(ev.docsExamined / Math.max(ev.nreturned, 1)).toLocaleString("en-US")}:1`;
}

function fence(code, lang = "js") {
  return "```" + lang + "\n" + code.trimEnd() + "\n```";
}

/** Markdown summary for a case comment. Contains the query text as given — review before pasting. */
export function toMarkdown(rep) {
  const L = [];
  const counts = severityCounts(rep).map(([s, n]) => `${n} ${s}`).join(", ") || "no open findings";
  L.push(`**MQL optimizer (static review)** — ${rep.inputQueries} quer${rep.inputQueries === 1 ? "y" : "ies"}, ${counts}` +
    (rep.applied.length ? `, ${rep.applied.length} safe rewrite(s)` : ""));
  L.push("");
  if (rep.interpreted !== null) {
    L.push(`Input: ${kindLabel(rep.inputKind)}, read as:`);
    L.push(fence(rep.interpreted));
  }
  rep.evidence.forEach((ev, i) => {
    if (!Object.keys(ev).length) return;
    const bits = [];
    if (ev.planSummary !== undefined) bits.push(`plan \`${ev.planSummary}\``);
    if (ev.durationMillis !== undefined) bits.push(`${ev.durationMillis} ms`);
    if (ev.docsExamined !== undefined) bits.push(`docsExamined ${ev.docsExamined}`);
    if (ev.keysExamined !== undefined) bits.push(`keysExamined ${ev.keysExamined}`);
    if (ev.nreturned !== undefined) bits.push(`nreturned ${ev.nreturned}`);
    const r = scanRatio(ev);
    if (r) bits.push(`scan ratio ${r}`);
    L.push(`Logged evidence${rep.evidence.length > 1 ? ` (query ${i + 1})` : ""}: ${bits.join(", ")}`);
  });
  const findings = rep.findings.filter((f) => !f.code.endsWith("-rewrite"));
  if (findings.length) {
    L.push("", "**Findings**");
    for (const f of findings) {
      const doc = docFor(f.code);
      L.push(`- **${f.severity.toUpperCase()}** \`${f.code}\` (${f.pass}): ${f.message}${doc ? ` [MongoDB docs](${doc})` : ""}`);
    }
  }
  if (rep.applied.length) {
    L.push("", "**Safe rewrites (same results)**");
    for (const f of rep.applied) L.push(`- \`${f.code}\`: ${f.message.split(". ")[0].replace(/\.+$/, "")}.`);
    L.push("", "Rewritten:", fence(rep.text));
  }
  if (rep.indexes.length) {
    L.push("", `**Index recommendations** (test on non-production first; check existing indexes) — [ESR guideline](${ESR_DOC})`);
    for (const r of rep.indexes) L.push(fence(r.shell()), `_${r.rationale}_`);
  }
  L.push("", "_Static analysis only. Confirm with `explain(\"executionStats\")`: COLLSCAN → IXSCAN, " +
    "totalDocsExamined / nReturned near 1, nReturned unchanged._");
  return L.join("\n");
}
