// app — the full-page MongoDB Expertise app: search, documents, recipes, optimizer, lint, operators, about.
import { consumeHandoff, truncateText } from "./lib/capture.js";
import { analyze, diagnosticsToDicts, symbolsToDicts } from "./lib/analyze.js";
import { OPERATORS } from "./lib/operators.js";
import { optimize } from "./lib/optimize.js";
import { getIndex } from "./lib/store.js";
import { embedQuery, EmbedError, snippet } from "./lib/textsearch.js";
import { copyButton, h, markFor, advanceMarkdownContext, renderMarkdown, renderReport } from "./lib/ui.js";

const $ = (id) => document.getElementById(id);
const TABS = ["search", "doc", "recipes", "optimize", "lint", "operators", "about"];
const KINDS = [[null, "all"], ["skill", "skills"], ["llms", "docs & facts"], ["recipe", "recipes"]];
const EXAMPLE_LOG = '{"t":{"$date":"2026-10-14T09:12:44Z"},"msg":"Slow query","attr":{"ns":"shop.orders","command":' +
  '{"find":"orders","filter":{"customerId":4711,"status":{"$ne":"cancelled"}},"sort":{"createdAt":-1},"skip":2000,' +
  '"limit":20,"$db":"shop"},"planSummary":"COLLSCAN","keysExamined":0,"docsExamined":1843220,"hasSortStage":true,' +
  '"nreturned":20,"durationMillis":4981}}';
const EXAMPLE_LINT = `db.orders.aggregate([
  { $match: { status: "A", qty: { $gtt: 5 } } },
  { $group: { total: { $sum: "$amount" } } },
  { $out: "report" },
  { $limit: 10 }
])
db.orders.updateOne({ _id: 1 }, { $set: { qty: 1 }, note: "x" })`;

const state = { q: "", kind: null, source: null, mode: "keyword", hits: [], selected: -1, lastSearchHash: "#search",
  settings: { semantic: false, host: "http://127.0.0.1:11434" } };
let index = null;
let indexProblem = "";
let searchGeneration = 0;
let routeGeneration = 0;
let documentGeneration = 0;
let settingsGeneration = 0;
let settingsWrites = Promise.resolve();
const truncatedInputs = new Map();
function setToolInput(id, text, truncated = false) {
  $(id).value = text;
  if (truncated) truncatedInputs.set(id, text);
  else truncatedInputs.delete(id);
}
function isTruncatedInput(id) {
  const yes = truncatedInputs.has(id) && truncatedInputs.get(id) === $(id).value;
  if (!yes) truncatedInputs.delete(id);
  return yes;
}
function inputWarning(id) {
  return isTruncatedInput(id) ? h("p", { class: "status error" }, "Only the first 200,000 characters of the selection were checked.") : document.createDocumentFragment();
}

// ---------------------------------------------------------------- routing

function parseHash() {
  const raw = location.hash.replace(/^#/, "");
  const [tab, qs] = raw.split("?");
  return { tab: TABS.includes(tab) ? tab : "search", params: new URLSearchParams(qs || "") };
}

function go(tab, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== null && v !== undefined));
  const hash = `#${tab}${[...qs].length ? "?" + qs : ""}`;
  if (location.hash === hash) route();
  else location.hash = hash;
}

function showTab(tab) {
  for (const t of TABS) $(`tab-${t}`).hidden = t !== tab;
  for (const a of document.querySelectorAll(".tabs a")) {
    const active = a.dataset.tab === (tab === "doc" ? "search" : tab);
    a.setAttribute("aria-selected", String(active));
    a.setAttribute("tabindex", active ? "0" : "-1");
  }
}

async function route() {
  const generation = ++routeGeneration;
  ++searchGeneration;
  ++documentGeneration;
  const { tab, params } = parseHash();
  showTab(tab);
  if (tab === "search") {
    const q = params.get("q") ?? state.q;
    state.kind = params.get("kind") || null;
    state.source = params.get("source") || null;
    if (params.get("mode")) state.mode = params.get("mode");
    $("q").value = q;
    $("mode").value = state.mode;
    state.lastSearchHash = location.hash || "#search";
    if (!q.trim()) {
      await runSearch(q);
      $("q").focus();
      await renderFacets(generation);
      return;
    }
    await renderFacets(generation);
    if (generation !== routeGeneration) return;
    await runSearch(q);
  } else if (tab === "doc") {
    await showDocument(params.get("path"), Number(params.get("line") || 0), params.get("q") || "");
  } else if (tab === "recipes") {
    await renderRecipes();
  } else if (tab === "operators") {
    renderOperators();
  } else if (tab === "about") {
    await renderAbout();
  } else if (tab === "optimize" && params.get("text")) {
    $("opt-input").value = params.get("text");
    runOptimize();
  }
}

// ---------------------------------------------------------------- index

async function ensureIndex() {
  if (index) return index;
  try {
    index = await getIndex();
    indexProblem = index ? "" : "This build has no search data.";
  } catch {
    indexProblem = "Could not load the packaged index. Try again.";
    return null;
  }
  return index;
}

// ---------------------------------------------------------------- search

async function renderFacets(generation = routeGeneration) {
  const idx = await ensureIndex();
  if (generation !== routeGeneration) return;
  const kinds = $("kinds");
  kinds.replaceChildren(...KINDS.map(([k, label]) => h("button", { type: "button", "aria-pressed": String(state.kind === k),
    onclick: () => go("search", { q: $("q").value, kind: k, mode: state.mode }) }, label)));
  $("clear-scope").hidden = !state.source;
  if (!idx) return;
  const filter = $("facet-filter").value.trim().toLowerCase();
  const items = idx.facets().filter((s) => (!state.kind || s.kind === state.kind) && (!filter || s.source.toLowerCase().includes(filter)));
  $("sources").replaceChildren(...items.map((s) => h("li", {
    title: `${s.source} — ${s.chunks} passages (${s.kind})`, "aria-selected": String(state.source === s.source),
    onclick: () => go("search", { q: $("q").value, kind: state.kind, source: state.source === s.source ? null : s.source, mode: state.mode }),
  }, h("span", { class: "name" }, s.source), h("span", { class: "n" }, s.chunks.toLocaleString()))));
}

async function queryVector(q, idx, mode, settings) {
  if (mode === "keyword") return { qv: null, note: "" };
  if (!settings.semantic) {
    return { qv: null, note: " · semantic search is off (About → Semantic and hybrid search); showing keyword results" };
  }
  try {
    const model = (idx.meta.vectors && idx.meta.vectors.model) || "nomic-embed-text";
    const qv = await embedQuery(q, { host: settings.host, model });
    if (!Array.isArray(qv) || qv.length !== idx.dim || !qv.every(Number.isFinite)) throw new EmbedError("the query embedding does not match the index");
    return { qv, note: "" };
  } catch (err) {
    const msg = err instanceof EmbedError ? err.message : String(err);
    return { qv: null, note: ` · ${msg}; showing keyword results` };
  }
}

async function runSearch(q) {
  const generation = ++searchGeneration;
  const settings = { ...state.settings };
  const opts = { kind: state.kind, source: state.source };
  let mode = state.mode;
  state.q = q;
  state.hits = [];
  state.selected = -1;
  $("results").replaceChildren();
  $("detail").replaceChildren();
  const status = $("search-status");
  status.classList.remove("error");
  if (!q.trim()) { status.textContent = ""; return; }
  status.textContent = "Searching the MongoDB expertise index…";
  const idx = await ensureIndex();
  if (generation !== searchGeneration) return;
  if (!idx) { status.textContent = indexProblem; status.classList.add("error"); return; }
  if (!idx.vectors && mode !== "keyword") mode = "keyword";
  const { qv, note } = await queryVector(q, idx, mode, settings);
  if (generation !== searchGeneration) return;
  const t0 = performance.now();
  let hits;
  if (mode === "semantic" && qv) hits = idx.semanticVec(qv, 40, opts);
  else if (mode === "hybrid" && qv) hits = idx.hybridVec(q, qv, 40, opts);
  else hits = idx.keyword(q, 40, opts);
  const ms = Math.round(performance.now() - t0);
  state.hits = hits;
  const scope = [opts.kind && `kind ${opts.kind}`, opts.source && `area ${opts.source}`].filter(Boolean).join(", ");
  status.textContent = `${hits.length} result${hits.length === 1 ? "" : "s"} in ${ms} ms${scope ? ` · ${scope}` : ""}${note}`;
  $("results").replaceChildren(...hits.map((hit, i) => h("li", { "data-i": i, onclick: () => select(i) },
    h("div", { class: "meta" }, h("span", { class: `chip k-${hit.kind}` }, hit.kind), h("span", { class: "src" }, hit.source),
      h("span", {}, hit.score.toFixed(3)), hit.via !== "keyword" ? h("span", {}, hit.via) : null),
    h("div", { class: "heading" }, hit.heading.split(" > ").slice(-1)[0]),
    h("div", { class: "snip" }, snippet(hit.text, q).map((s) => (s.hit ? h("mark", {}, s.text) : s.text))))));
  if (hits.length) select(0);
  else $("detail").replaceChildren(h("p", { class: "status" }, "No matches. Try fewer words, another area, or clear the kind filter."));
}

function select(i) {
  state.selected = i;
  for (const li of $("results").children) li.setAttribute("aria-selected", String(Number(li.dataset.i) === i));
  const hit = state.hits[i];
  if (!hit) return;
  $("results").children[i]?.scrollIntoView({ block: "nearest" });
  const cite = `${hit.path}:${hit.line} — ${hit.heading}`;
  const body = h("div", { class: "md" });
  const context = { fence: null };
  const chunks = index?.document(hit.path)?.chunks || [];
  for (const chunk of chunks) {
    if (chunk.id === hit.id || chunk.line >= hit.line) break;
    advanceMarkdownContext(chunk.text, { context, line: chunk.line });
  }
  body.append(renderMarkdown(hit.text, { mark: markFor(state.q), context, line: hit.line }));
  $("detail").replaceChildren(
    h("div", { class: "crumb" }, hit.heading),
    h("div", { class: "loc" }, `${hit.path}:${hit.line}`),
    h("div", { class: "row" },
      h("button", { type: "button", class: "small primary", onclick: () => go("doc", { path: hit.path, line: hit.line, q: state.q }) }, "Open document"),
      copyButton(() => cite, "Copy citation"), copyButton(() => hit.text, "Copy passage"),
      h("button", { type: "button", class: "small", onclick: () => go("search", { q: state.q, source: hit.source, mode: state.mode }) }, `More from ${hit.source}`)),
    body);
}

// ---------------------------------------------------------------- documents

async function showDocument(path, line, q) {
  const generation = ++documentGeneration;
  $("doc-title").textContent = "";
  $("doc-actions").replaceChildren();
  const docEl = $("doc");
  docEl.replaceChildren();
  const idx = await ensureIndex();
  if (generation !== documentGeneration) return;
  if (!idx || !path) {
    docEl.replaceChildren(h("p", { class: "status error" }, "Document not found."));
    return;
  }
  const d = idx.document(path);
  if (!d) {
    docEl.replaceChildren(h("p", { class: "status error" }, `${path} is not in the packaged corpus.`));
    return;
  }
  $("doc-title").textContent = `${path} · ${d.source}`;
  $("doc-actions").replaceChildren(copyButton(() => d.chunks.map((c) => c.text).join("\n\n"), "Copy document"));
  const mark = markFor(q);
  let target = null;
  const context = { fence: null };
  docEl.replaceChildren(...d.chunks.map((c, i) => {
    const isTarget = line && (c.line === line || (c.line <= line && (d.chunks[i + 1]?.line ?? Infinity) > line));
    const el = h("section", { class: `chunk md${isTarget ? " target" : ""}`, id: `L${c.line}` });
    el.append(renderMarkdown(c.text, { mark: isTarget ? mark : null, context, line: c.line }));
    if (isTarget && !target) target = el;
    return el;
  }));
  if (target) requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  else docEl.scrollTop = 0;
}

// ---------------------------------------------------------------- recipes

async function renderRecipes() {
  const idx = await ensureIndex();
  const list = $("recipes");
  list.dataset.ready = "false";
  if (!idx) {
    list.replaceChildren(h("li", {}, "No index packaged."));
    list.dataset.ready = "true";
    return;
  }
  const f = $("recipe-filter").value.trim().toLowerCase();
  const items = idx.meta.recipes.filter((r) => !f || `${r.name} ${r.title} ${r.summary}`.toLowerCase().includes(f));
  list.replaceChildren(...items.map((r) => h("li", { tabindex: "0", onclick: () => go("doc", { path: r.path }),
    onkeydown: (e) => { if (e.key === "Enter") go("doc", { path: r.path }); } },
  h("h3", {}, r.title), h("p", {}, r.summary), h("span", { class: "kind" }, (r.applies_to || []).join(" · ")))));
  list.dataset.ready = "true";
}

// ---------------------------------------------------------------- optimizer

function refLink(ref) {
  return h("a", { href: `#doc?path=${encodeURIComponent(ref)}` }, "Read more in the corpus");
}

function runOptimize() {
  const text = $("opt-input").value;
  $("opt-out").replaceChildren();
  if (!text.trim()) return;
  let rep;
  try {
    rep = optimize(text);
  } catch (err) {
    $("opt-out").replaceChildren(h("p", { class: "status error" }, `The optimizer could not read this input: ${err.message}`));
    return;
  }
  $("opt-out").replaceChildren(inputWarning("opt-input"), renderReport(rep, { refLink,
    extra: h("button", { type: "button", class: "small", onclick: () => { setToolInput("lint-input", text, isTruncatedInput("opt-input")); go("lint"); runLint(); } }, "Lint this") }));
}

// ---------------------------------------------------------------- lint

function runLint() {
  const text = $("lint-input").value;
  const out = $("lint-out");
  if (!text.trim()) {
    out.replaceChildren();
    return;
  }
  const res = analyze(text);
  const diags = diagnosticsToDicts(text, res.diagnostics);
  const symbols = symbolsToDicts(res.symbols);
  const outline = (syms) => h("ul", {}, syms.map((s) => h("li", {}, h("code", {}, s.name), ` ${s.kind}`, s.children?.length ? outline(s.children) : null)));
  const fragment = document.createDocumentFragment();
  fragment.append(h("div", { class: "summary" }, diags.length ? ["error", "warning", "info", "hint"].map((sev) => {
      const n = diags.filter((d) => d.severity === sev).length;
      return n ? h("span", { class: `chip sev-${sev}` }, `${n} ${sev}`) : null;
    }) : h("span", { class: "chip ok" }, "no problems found")));
  for (const d of diags) fragment.append(h("div", { class: `diag sev-${d.severity}` },
      h("div", { class: "head" }, `${d.line + 1}:${d.column + 1} ${d.severity.toUpperCase()} · ${d.code}`),
      h("p", {}, d.message, d.fix ? [" ", h("code", {}, d.fix)] : null)));
  if (symbols.length) fragment.append(h("h2", {}, "Outline"), outline(symbols));
  out.replaceChildren(inputWarning("lint-input"), fragment);
}

// ---------------------------------------------------------------- operators

function renderOperators() {
  const f = $("op-filter").value.trim().toLowerCase();
  const ops = [...OPERATORS.values()].filter((o) => !f || `${o.name} ${[...o.cats].join(" ")} ${o.doc}`.toLowerCase().includes(f))
    .sort((a, b) => a.name.localeCompare(b.name));
  $("op-count").textContent = `${ops.length} of ${OPERATORS.size} operators`;
  $("ops").replaceChildren(...ops.map((o) => h("li", {},
    h("div", {}, h("div", { class: "name" }, o.name), h("div", { class: "cats" }, [...o.cats].sort().map((c) => h("span", {}, c)))),
    h("div", {}, o.doc, h("div", { class: "kind" }, `argument: ${o.arg}`)),
    h("button", { type: "button", class: "small", onclick: () => go("search", { q: o.name, mode: state.mode }) }, "Search corpus"))));
}

// ---------------------------------------------------------------- about + settings

async function loadSettings() {
  const generation = settingsGeneration;
  try {
    const { settings } = await chrome.storage.local.get("settings");
    if (generation !== settingsGeneration) return;
    if (settings) Object.assign(state.settings, settings);
  } catch { /* defaults */ }
  if (state.settings.semantic) state.mode = "hybrid";
}

function saveSettings(next = state.settings) {
  const settings = { ...next };
  const write = settingsWrites.then(() => chrome.storage.local.set({ settings }));
  settingsWrites = write.catch(() => {});
  return write;
}

function originPattern(host) {
  const u = new URL(host);
  return `${u.protocol}//${u.hostname}/*`;
}

async function renderAbout() {
  $("ollama-host").value = state.settings.host;
  $("ollama-status").textContent = state.settings.semantic ? `On — using ${state.settings.host}` : "Off — keyword search only.";
  const idx = await ensureIndex();
  const m = idx ? idx.meta : null;
  const row = (k, v) => [h("dt", {}, k), h("dd", {}, v)];
  $("stats").replaceChildren(...(m ? [
    row("Passages", m.chunks.toLocaleString()), row("Files", m.files.toLocaleString()), row("Areas", String(m.sources.length)),
    row("By kind", Object.entries(m.by_kind).map(([k, n]) => `${k} ${n.toLocaleString()}`).join(" · ")),
    row("Vocabulary", `${m.terms.toLocaleString()} terms, ${m.postings.toLocaleString()} postings`),
    row("Vectors", m.vectors ? `${m.vectors.count.toLocaleString()} × ${m.vectors.dim} (${m.vectors.model || "unknown model"})` : "none (keyword only)"),
    row("Recipes", String(m.recipes.length)), row("Built", `${m.built_at} by mdbx ${m.mdbx_version}`),
    row("Extension", chrome.runtime.getManifest().version),
  ].flat() : row("Index", "not packaged")));
}

function showOllamaHelp(show) {
  const box = $("ollama-help");
  box.hidden = !show;
  if (!show) return;
  const id = chrome.runtime.id;
  const mac = `launchctl setenv OLLAMA_ORIGINS "chrome-extension://${id}"`;
  const linuxEdit = "sudo systemctl edit ollama";
  const linuxOverride = `[Service]\nEnvironment="OLLAMA_ORIGINS=chrome-extension://${id}"`;
  const linuxRestart = "sudo systemctl restart ollama";
  box.replaceChildren(
    h("p", {}, "Ollama only accepts requests from origins it trusts. Allow this extension, then restart Ollama:"),
    h("div", { class: "row" }, h("code", {}, mac), copyButton(() => mac)),
    h("p", {}, "Linux: open the service override editor:"),
    h("div", { class: "row" }, h("code", {}, linuxEdit), copyButton(() => linuxEdit)),
    h("p", {}, "Paste only these override contents into the editor, then save:"),
    h("div", { class: "row" }, h("code", {}, linuxOverride), copyButton(() => linuxOverride)),
    h("p", {}, "After saving, restart the service:"),
    h("div", { class: "row" }, h("code", {}, linuxRestart), copyButton(() => linuxRestart)),
    h("p", { class: "kind" }, "On Windows set the OLLAMA_ORIGINS user environment variable to the same value. Then click Enable and test again."));
}

async function enableOllama() {
  const generation = ++settingsGeneration;
  const host = $("ollama-host").value.trim().replace(/\/$/, "");
  const status = $("ollama-status");
  status.classList.remove("error");
  let pattern;
  try {
    pattern = originPattern(host);
  } catch {
    status.textContent = "Enter a URL such as http://127.0.0.1:11434.";
    status.classList.add("error");
    return;
  }
  const granted = await chrome.permissions.request({ origins: [pattern] }).catch(() => false);
  if (generation !== settingsGeneration) return;
  if (!granted) {
    status.textContent = "Permission to reach that address was not granted.";
    status.classList.add("error");
    return;
  }
  const idx = await ensureIndex();
  if (generation !== settingsGeneration) return;
  const model = (idx && idx.meta.vectors && idx.meta.vectors.model) || "nomic-embed-text";
  status.textContent = `Testing ${host} with ${model}…`;
  try {
    const v = await embedQuery("ping", { host, model });
    if (generation !== settingsGeneration) return;
    if (!Array.isArray(v) || !v.every(Number.isFinite)) throw new EmbedError("the model returned an invalid embedding");
    if (idx && idx.dim && v.length !== idx.dim) throw new EmbedError(`the model returned ${v.length} dimensions but the index has ${idx.dim}; pull ${model}`);
    const settings = { semantic: true, host };
    await saveSettings(settings);
    if (generation !== settingsGeneration) return;
    state.settings = settings;
    state.mode = "hybrid";
    showOllamaHelp(false);
    status.textContent = `On — ${host} answered with ${v.length}-dimension ${model} embeddings. Hybrid is now the default search mode.`;
  } catch (err) {
    if (generation !== settingsGeneration) return;
    status.textContent = err.message;
    status.classList.add("error");
    showOllamaHelp(/403/.test(err.message));
  }
}

async function disableOllama() {
  const generation = ++settingsGeneration;
  ++searchGeneration;
  state.settings = { ...state.settings, semantic: false };
  state.mode = "keyword";
  const status = $("ollama-status");
  status.classList.remove("error");
  status.textContent = "Off — keyword search only.";
  try {
    await saveSettings();
  } catch {
    if (generation !== settingsGeneration) return;
    status.textContent = "Off for this session. Saving failed; the previous setting may return after reopening.";
    status.classList.add("error");
  }
}

// ---------------------------------------------------------------- startup

async function consumePending() {
  try {
    const { params } = parseHash();
    const appPending = await consumeHandoff(chrome.storage.session, params.get("handoff"));
    if (!appPending) return false;
    if (appPending.tab === "lint") {
      setToolInput("lint-input", appPending.text, appPending.truncated);
      go("lint");
      runLint();
    } else if (appPending.tab === "optimize") {
      setToolInput("opt-input", appPending.text, appPending.truncated);
      go("optimize");
      runOptimize();
    } else {
      go("search", { q: truncateText(appPending.text, 500) });
    }
    return true;
  } catch {
    return false;
  }
}

function wire() {
  const tabs = [...document.querySelectorAll(".tabs a")];
  tabs.forEach((tab, i) => tab.addEventListener("keydown", e => {
    let next;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (i + tabs.length - 1) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    tabs[next].focus();
    go(tabs[next].dataset.tab);
  }));
  $("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    go("search", { q: $("q").value, kind: state.kind, source: state.source, mode: $("mode").value });
  });
  $("mode").addEventListener("change", () => { state.mode = $("mode").value; go("search", { q: $("q").value, kind: state.kind, source: state.source, mode: state.mode }); });
  $("facet-filter").addEventListener("input", () => renderFacets());
  $("clear-scope").addEventListener("click", () => go("search", { q: $("q").value, kind: state.kind, mode: state.mode }));
  $("doc-back").addEventListener("click", () => { if (history.length > 1) history.back(); else location.hash = state.lastSearchHash; });
  $("recipe-filter").addEventListener("input", () => renderRecipes());
  $("op-filter").addEventListener("input", () => renderOperators());
  $("opt-run").addEventListener("click", runOptimize);
  $("opt-example").addEventListener("click", () => { setToolInput("opt-input", EXAMPLE_LOG); runOptimize(); });
  $("lint-run").addEventListener("click", runLint);
  $("lint-to-opt").addEventListener("click", () => { setToolInput("opt-input", $("lint-input").value, isTruncatedInput("lint-input")); go("optimize"); runOptimize(); });
  $("ollama-enable").addEventListener("click", enableOllama);
  $("ollama-disable").addEventListener("click", disableOllama);
  for (const [id, fn] of [["opt-input", runOptimize], ["lint-input", runLint]]) {
    $(id).addEventListener("input", () => truncatedInputs.delete(id));
    $(id).addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) fn(); });
  }
  document.addEventListener("keydown", (e) => {
    if ($("tab-search").hidden || e.defaultPrevented) return;
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (e.key === "/" && !typing) { e.preventDefault(); $("q").focus(); $("q").select(); }
    else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && state.hits.length && document.activeElement !== $("facet-filter") && (!typing || document.activeElement === $("q"))) {
      e.preventDefault();
      select(Math.max(0, Math.min(state.hits.length - 1, state.selected + (e.key === "ArrowDown" ? 1 : -1))));
    } else if (e.key === "Enter" && !typing && !["BUTTON", "A", "SUMMARY"].includes(document.activeElement?.tagName) && !document.activeElement?.isContentEditable && state.hits[state.selected]) {
      const hit = state.hits[state.selected];
      go("doc", { path: hit.path, line: hit.line, q: state.q });
    } else if (e.key === "Escape" && state.source) {
      go("search", { q: $("q").value, kind: state.kind, mode: state.mode });
    }
  });
  window.addEventListener("hashchange", route);
}

async function main() {
  wire();
  $("lint-input").value = EXAMPLE_LINT;
  await loadSettings();
  if (!(await consumePending())) await route();
  document.body.dataset.ready = "true";
}

main();
