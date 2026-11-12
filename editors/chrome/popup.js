// popup — capture the highlighted text; optimize it when it is a query, otherwise search the corpus for it.
import { clamp, consumeHandoff, grabSelection, pickSelection, truncateText } from "./lib/capture.js";
import { optimize } from "./lib/optimize.js";
import { getIndex } from "./lib/store.js";
import { snippet } from "./lib/textsearch.js";
import { h, renderReport } from "./lib/ui.js";

const EXAMPLE = '{"t":{"$date":"2026-10-14T09:12:44.118+00:00"},"s":"I","c":"COMMAND","id":51803,"msg":"Slow query",' +
  '"attr":{"ns":"shop.orders","command":{"find":"orders","filter":{"customerId":4711,"status":{"$ne":"cancelled"}},' +
  '"sort":{"createdAt":-1},"skip":2000,"limit":20,"$db":"shop"},"planSummary":"COLLSCAN","keysExamined":0,' +
  '"docsExamined":1843220,"hasSortStage":true,"nreturned":20,"durationMillis":4981}}';

let runGeneration = 0;

const $ = (id) => document.getElementById(id);

function setStatus(text, error = false) {
  const s = $("status");
  s.textContent = text;
  s.classList.toggle("error", error);
  s.hidden = !text;
}

function openApp(hash = "#search") {
  chrome.tabs.create({ url: chrome.runtime.getURL(`app.html${hash}`) });
  window.close();
}

function docLink(hash, label) {
  return h("a", { href: chrome.runtime.getURL(`app.html${hash}`), onclick: e => {
    if (e.defaultPrevented || e.button > 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault(); openApp(hash);
  } }, label);
}

function refLink(ref) {
  return docLink(`#doc?path=${encodeURIComponent(ref)}`, "Read more in the corpus");
}

async function readSelection() {
  // 1. Right-click "Optimize selected MQL" hands the text over through session storage.
  try {
    const params = new URLSearchParams(location.hash.split("?")[1] || "");
    const pending = await consumeHandoff(chrome.storage.session, params.get("handoff"));
    if (pending) return { text: pending.text, truncated: pending.truncated, from: "the right-click selection" };
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
    if (last) return { ...(typeof last === "string" ? { text: last } : last), from: "the last query you checked" };
  } catch { /* ignore */ }
  return { text: "", from: null };
}

/** The selection was not a query: show the best corpus passages for it instead. */
async function renderCorpusHits(text, generation = runGeneration) {
  const root = $("result");
  const q = truncateText(text.replace(/\s+/g, " ").trim(), 300);
  root.replaceChildren(h("p", { class: "status" }, "Not a query — searching MongoDB expertise for it…"));
  root.hidden = false;
  let idx;
  try { idx = await getIndex(); }
  catch {
    if (generation === runGeneration) root.replaceChildren(h("p", { class: "status error" }, "Could not load the search data. Try again."));
    return;
  }
  if (generation !== runGeneration) return;
  if (!idx) {
    root.replaceChildren(h("p", { class: "status error" }, "No query found, and this build has no search data."));
    return;
  }
  const hits = idx.keyword(q, 5);
  root.replaceChildren(
    h("div", { class: "summary" }, h("strong", {}, "MongoDB expertise"), h("span", { class: "kind" }, `· top ${hits.length} for your selection`)),
    hits.length ? h("ol", { class: "hits" }, hits.map((hit) => h("li", {},
      docLink(`#doc?path=${encodeURIComponent(hit.path)}&line=${hit.line}&q=${encodeURIComponent(q)}`, hit.heading.split(" > ").slice(-1)[0]),
      h("div", { class: "kind" }, `${hit.source} · ${hit.kind}`),
      h("div", { class: "snip" }, snippet(hit.text, q).map((s) => (s.hit ? h("mark", {}, s.text) : s.text))))))
      : h("p", { class: "status" }, "No matches in the corpus."),
    h("div", { class: "row" }, h("button", { type: "button", class: "small primary", onclick: () => openApp(`#search?q=${encodeURIComponent(q)}`) }, "Open all results in the app")));
}

function run(text, from, priorTruncated = false) {
  const generation = ++runGeneration;
  $("result").replaceChildren();
  $("result").hidden = true;
  const bounded = clamp(text);
  const input = bounded.text, truncated = Boolean(priorTruncated || bounded.truncated);
  $("input").value = input;
  if (!input.trim()) {
    setStatus("Highlight a query or a question on the page and click the extension again, or paste below.");
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
  $("input-section").open = false;
  const malformedQuery = /^\s*(?:[\[{]|db\s*(?:\.|\[))/.test(input) && rep.findings?.some(f => f.code === "syntax");
  if (!rep.inputQueries && !malformedQuery) {
    renderCorpusHits(input, generation);
  } else {
    const root = $("result");
    root.replaceChildren(renderReport(rep, { refLink }));
    root.hidden = false;
    if (!rep.inputQueries) $("input-section").open = true;
  }
  chrome.storage?.session?.set({ last: { text: input, truncated } }).catch(() => {});
}

async function main() {
  if (location.hash.split("?")[0] === "#tab") document.body.classList.add("tab");
  $("run").addEventListener("click", () => run($("input").value, "the edited input"));
  $("example").addEventListener("click", () => run(EXAMPLE, "the example slow-query log line"));
  $("input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run($("input").value, "the edited input");
  });
  $("open-app").addEventListener("click", () => openApp());
  $("ask").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("ask-q").value.trim();
    if (q) openApp(`#search?q=${encodeURIComponent(truncateText(q, 500))}`);
  });
  const { text, from, truncated } = await readSelection();
  run(text, from, truncated);
}

main();
