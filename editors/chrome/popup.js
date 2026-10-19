// popup — capture the highlighted text; optimize it when it is a query, otherwise search the corpus for it.
import { clamp, freshPending, grabSelection, pickSelection } from "./lib/capture.js";
import { optimize } from "./lib/optimize.js";
import { getIndex } from "./lib/store.js";
import { snippet } from "./lib/textsearch.js";
import { h, renderReport } from "./lib/ui.js";

const EXAMPLE = '{"t":{"$date":"2026-10-14T09:12:44.118+00:00"},"s":"I","c":"COMMAND","id":51803,"msg":"Slow query",' +
  '"attr":{"ns":"shop.orders","command":{"find":"orders","filter":{"customerId":4711,"status":{"$ne":"cancelled"}},' +
  '"sort":{"createdAt":-1},"skip":2000,"limit":20,"$db":"shop"},"planSummary":"COLLSCAN","keysExamined":0,' +
  '"docsExamined":1843220,"hasSortStage":true,"nreturned":20,"durationMillis":4981}}';

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

function refLink(ref) {
  return h("a", { href: "#", onclick: (e) => { e.preventDefault(); openApp(`#doc?path=${encodeURIComponent(ref)}`); } },
    "Read more in the corpus");
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

/** The selection was not a query: show the best corpus passages for it instead. */
async function renderCorpusHits(text) {
  const root = $("result");
  const q = text.replace(/\s+/g, " ").trim().slice(0, 300);
  root.replaceChildren(h("p", { class: "status" }, "Not a query — searching MongoDB expertise for it…"));
  root.hidden = false;
  const idx = await getIndex().catch(() => null);
  if (!idx) {
    root.replaceChildren(h("p", { class: "status error" }, "No query found, and this build has no search data."));
    return;
  }
  const hits = idx.keyword(q, 5);
  root.replaceChildren(
    h("div", { class: "summary" }, h("strong", {}, "MongoDB expertise"), h("span", { class: "kind" }, `· top ${hits.length} for your selection`)),
    hits.length ? h("ol", { class: "hits" }, hits.map((hit) => h("li", {},
      h("a", { href: "#", onclick: (e) => { e.preventDefault(); openApp(`#doc?path=${encodeURIComponent(hit.path)}&line=${hit.line}&q=${encodeURIComponent(q)}`); } },
        hit.heading.split(" > ").slice(-1)[0]),
      h("div", { class: "kind" }, `${hit.source} · ${hit.kind}`),
      h("div", { class: "snip" }, snippet(hit.text, q).map((s) => (s.hit ? h("mark", {}, s.text) : s.text))))))
      : h("p", { class: "status" }, "No matches in the corpus."),
    h("div", { class: "row" }, h("button", { type: "button", class: "small primary", onclick: () => openApp(`#search?q=${encodeURIComponent(q)}`) }, "Open all results in the app")));
}

function run(text, from) {
  const { text: input, truncated } = clamp(text);
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
  if (!rep.inputQueries) {
    renderCorpusHits(input);
  } else {
    const root = $("result");
    root.replaceChildren(renderReport(rep, { refLink }));
    root.hidden = false;
  }
  chrome.storage?.session?.set({ last: input }).catch(() => {});
}

async function main() {
  if (location.hash === "#tab") document.body.classList.add("tab");
  $("run").addEventListener("click", () => run($("input").value, "the edited input"));
  $("example").addEventListener("click", () => run(EXAMPLE, "the example slow-query log line"));
  $("input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run($("input").value, "the edited input");
  });
  $("open-app").addEventListener("click", () => openApp());
  $("ask").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("ask-q").value.trim();
    if (q) openApp(`#search?q=${encodeURIComponent(q)}`);
  });
  const { text, from } = await readSelection();
  run(text, from);
}

main();
