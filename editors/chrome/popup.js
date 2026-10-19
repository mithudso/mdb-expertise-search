// popup — capture the highlighted query, run the optimizer locally and render the report.
import { clamp, freshPending, grabSelection, pickSelection } from "./lib/capture.js";
import { docFor, ESR_DOC } from "./lib/docs.js";
import { optimize } from "./lib/optimize.js";
import { kindLabel, scanRatio, severityCounts, toMarkdown } from "./lib/report.js";

const EXAMPLE = '{"t":{"$date":"2026-10-14T09:12:44.118+00:00"},"s":"I","c":"COMMAND","id":51803,"msg":"Slow query",' +
  '"attr":{"ns":"shop.orders","command":{"find":"orders","filter":{"customerId":4711,"status":{"$ne":"cancelled"}},' +
  '"sort":{"createdAt":-1},"skip":2000,"limit":20,"$db":"shop"},"planSummary":"COLLSCAN","keysExamined":0,' +
  '"docsExamined":1843220,"hasSortStage":true,"nreturned":20,"durationMillis":4981}}';

const $ = (id) => document.getElementById(id);

/** Build a DOM element. Children are nodes or strings (always inserted as text, never as HTML). */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

function setStatus(text, error = false) {
  const s = $("status");
  s.textContent = text;
  s.classList.toggle("error", error);
  s.hidden = !text;
}

async function copy(text, btn) {
  const label = btn.textContent;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copied";
  } catch {
    btn.textContent = "Copy failed";
  }
  setTimeout(() => { btn.textContent = label; }, 1500);
}

function copyButton(getText, label = "Copy") {
  const b = h("button", { type: "button", class: "small" }, label);
  b.addEventListener("click", () => copy(getText(), b));
  return b;
}

async function readSelection() {
  // 1. Right-click "Optimize selected MQL" hands the text over through session storage.
  try {
    const { pending } = await chrome.storage.session.get("pending");
    if (pending) await chrome.storage.session.remove("pending");
    if (freshPending(pending)) return { text: pending.text, from: "the right-click selection" };
  } catch { /* session storage unavailable: fall through */ }
  // 2. The highlighted text in the active tab (activeTab grants access because the user clicked us).
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id !== undefined && !String(tab.url || "").startsWith(chrome.runtime.getURL(""))) {
      let results;
      try {
        results = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, func: grabSelection });
      } catch {
        results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: grabSelection });
      }
      const text = pickSelection(results);
      if (text) return { text, from: "your selection" };
    }
  } catch { /* chrome:// pages, the Web Store and PDFs cannot be scripted */ }
  // 3. The last thing analysed in this browser session.
  try {
    const { last } = await chrome.storage.session.get("last");
    if (last) return { text: last, from: "the last query you checked" };
  } catch { /* ignore */ }
  return { text: "", from: null };
}

function renderEvidence(rep) {
  const blocks = [];
  rep.evidence.forEach((ev, i) => {
    if (!Object.keys(ev).length) return;
    const metric = (value, label) => (value === undefined || value === null ? null :
      h("div", { class: "metric" }, h("b", {}, String(value)), h("span", {}, label)));
    blocks.push(h("div", {},
      rep.evidence.length > 1 ? h("h2", {}, `Logged evidence — query ${i + 1}`) : h("h2", {}, "Logged evidence"),
      h("div", { class: "evidence" },
        metric(ev.planSummary, "plan"),
        metric(ev.durationMillis !== undefined ? `${ev.durationMillis} ms` : undefined, "duration"),
        metric(ev.docsExamined, "docsExamined"),
        metric(ev.keysExamined, "keysExamined"),
        metric(ev.nreturned, "nreturned"),
        metric(scanRatio(ev), "scanned : returned"))));
  });
  return blocks;
}

function renderFinding(f) {
  const doc = docFor(f.code);
  return h("div", { class: `finding sev-${f.severity}` },
    h("div", { class: "head" }, h("span", {}, f.severity.toUpperCase()), h("span", { class: "kind" }, `${f.pass} · ${f.code}`)),
    h("p", {}, f.message),
    doc ? h("a", { href: doc, target: "_blank", rel: "noopener noreferrer" }, "MongoDB docs") : null);
}

function render(rep) {
  const root = $("result");
  root.replaceChildren();
  const counts = severityCounts(rep);
  const findings = rep.findings.filter((f) => !f.code.endsWith("-rewrite"));

  if (!rep.inputQueries) {
    root.append(h("p", { class: "status error" },
      "No query found. Highlight a mongosh query (db.coll.find(…), aggregate([…])), a slow-query log line, " +
      "a profiler entry, a { find: … } command, a filter or a pipeline — or paste one below."));
    root.hidden = false;
    return;
  }

  root.append(h("div", { class: "summary" },
    h("strong", {}, `${rep.inputQueries} quer${rep.inputQueries === 1 ? "y" : "ies"}`),
    counts.length ? counts.map(([s, n]) => h("span", { class: `chip sev-${s}` }, `${n} ${s}`))
      : h("span", { class: "chip ok" }, "no open findings"),
    rep.applied.length ? h("span", { class: "chip ok" }, `${rep.applied.length} safe rewrite${rep.applied.length > 1 ? "s" : ""}`) : null,
    h("span", { class: "kind" }, `· ${kindLabel(rep.inputKind)}`)));

  root.append(h("div", { class: "row" },
    copyButton(() => toMarkdown(rep), "Copy as Markdown for the case"),
    rep.changed ? copyButton(() => rep.text, "Copy rewritten query") : null));

  if (rep.interpreted !== null) {
    root.append(h("h2", {}, `Read the ${kindLabel(rep.inputKind)} as`), h("pre", {}, rep.interpreted.trimEnd()));
  }
  root.append(...renderEvidence(rep));

  if (findings.length) {
    root.append(h("h2", {}, "Findings"), ...findings.map(renderFinding));
  }

  if (rep.applied.length) {
    root.append(h("h2", {}, "Safe rewrites applied (same results)"),
      h("ul", { class: "applied" }, rep.applied.map((f) => h("li", {}, `${f.message.split(". ")[0].replace(/\.+$/, "")}.`))),
      h("pre", {}, rep.text.trimEnd()));
  }

  if (rep.indexes.length) {
    root.append(h("h2", {}, "Index recommendations"),
      h("p", { class: "kind" }, "Recommend-only: check existing indexes and build on non-production first. ",
        h("a", { href: ESR_DOC, target: "_blank", rel: "noopener noreferrer" }, "ESR guideline")),
      ...rep.indexes.map((r) => h("div", { class: "index" },
        h("div", { class: "line" }, h("pre", {}, r.shell()), copyButton(() => r.shell())),
        h("p", {}, r.rationale))));
  }
  root.hidden = false;
}

function run(text, from) {
  const { text: input, truncated } = clamp(text);
  $("input").value = input;
  if (!input.trim()) {
    setStatus("Highlight a query on the page and click the extension again, or paste one below.");
    $("input-section").hidden = false;
    $("input-section").open = true;
    $("result").hidden = true;
    $("input").focus();
    return;
  }
  let rep;
  try {
    rep = optimize(input);
  } catch (err) {
    setStatus(`The optimizer could not read this input (${err && err.message ? err.message : err}). Edit it below and try again.`, true);
    $("input-section").hidden = false;
    $("input-section").open = true;
    return;
  }
  setStatus(from ? `Checked ${from}${truncated ? " (first 200,000 characters)" : ""}.` : "");
  $("input-label").textContent = "Edit the input or paste another query";
  $("input-section").hidden = false;
  $("input-section").open = !rep.inputQueries; // keep the editor open when nothing was recognised
  render(rep);
  chrome.storage?.session?.set({ last: input }).catch(() => {});
}

async function main() {
  if (location.hash === "#tab") document.body.classList.add("tab");
  $("run").addEventListener("click", () => run($("input").value, "the edited input"));
  $("example").addEventListener("click", () => run(EXAMPLE, "the example slow-query log line"));
  $("input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run($("input").value, "the edited input");
  });
  const { text, from } = await readSelection();
  run(text, from);
}

main();
