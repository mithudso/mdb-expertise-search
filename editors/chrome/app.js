// app — the full-page MongoDB Expertise app: search, documents, recipes, optimizer, lint, operators, about.
import { analyze, diagnosticsToDicts, symbolsToDicts } from "./lib/analyze.js";
import { OPERATORS } from "./lib/operators.js";
import { optimize } from "./lib/optimize.js";
import { getIndex } from "./lib/store.js";
import { embedQuery, EmbedError, snippet } from "./lib/textsearch.js";
import { copyButton, h, markFor, renderMarkdown, renderReport } from "./lib/ui.js";

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

// ---------------------------------------------------------------- routing

function parseHash() {
  const raw = location.hash.replace(/^#/, "");
  const [tab, qs] = raw.split("?");
  return { tab: TABS.includes(tab) ? tab : "search", params: new URLSearchParams(qs || "") };
}

function go(tab, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""));
  const hash = `#${tab}${[...qs].length ? "?" + qs : ""}`;
  if (location.hash === hash) route();
  else location.hash = hash;
}

function showTab(tab) {
  for (const t of TABS) $(`tab-${t}`).hidden = t !== tab;
  for (const a of document.querySelectorAll(".tabs a")) {
    a.setAttribute("aria-selected", String(a.dataset.tab === (tab === "doc" ? "search" : tab)));
  }
}

async function route() {
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
    await renderFacets();
    if (q.trim()) await runSearch(q);
    else $("q").focus();
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
  $("search-status").textContent = "Loading the MongoDB expertise index…";
  const t0 = performance.now();
  try {
    index = await getIndex();
  } catch (err) {
    index = null;
    $("search-status").textContent = `Could not load the index: ${err.message}`;
    $("search-status").classList.add("error");
    return null;
  }
  if (!index) {
    $("search-status").textContent = "This build has no search data. Rebuild it with python scripts/package_chrome_extension.py.";
    $("search-status").classList.add("error");
    return null;
  }
  $("search-status").textContent = `${index.n.toLocaleString()} passages from ${index.meta.files} files loaded in ${Math.round(performance.now() - t0)} ms.`;
  return index;
}

// ---------------------------------------------------------------- search

async function renderFacets() {
  const idx = await ensureIndex();
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

async function queryVector(q) {
  if (state.mode === "keyword") return { qv: null, note: "" };
  if (!state.settings.semantic) {
    return { qv: null, note: " · semantic search is off (About → Semantic and hybrid search); showing keyword results" };
  }
  try {
    const model = (index.meta.vectors && index.meta.vectors.model) || "nomic-embed-text";
    return { qv: await embedQuery(q, { host: state.settings.host, model }), note: "" };
  } catch (err) {
    const msg = err instanceof EmbedError ? err.message : String(err);
    return { qv: null, note: ` · ${msg}; showing keyword results` };
  }
}

async function runSearch(q) {
  const idx = await ensureIndex();
  if (!idx) return;
  state.q = q;
  const status = $("search-status");
  status.classList.remove("error");
  if (!idx.vectors && state.mode !== "keyword") state.mode = "keyword";
  const { qv, note } = await queryVector(q);
  const opts = { kind: state.kind, source: state.source };
  const t0 = performance.now();
  let hits;
  if (state.mode === "semantic" && qv) hits = idx.semanticVec(qv, 40, opts);
  else if (state.mode === "hybrid" && qv) hits = idx.hybridVec(q, qv, 40, opts);
  else hits = idx.keyword(q, 40, opts);
  const ms = Math.round(performance.now() - t0);
  state.hits = hits;
  const scope = [state.kind && `kind ${state.kind}`, state.source && `area ${state.source}`].filter(Boolean).join(", ");
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
  body.append(renderMarkdown(hit.text, { mark: markFor(state.q) }));
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
  const idx = await ensureIndex();
  const docEl = $("doc");
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
  docEl.replaceChildren(...d.chunks.map((c, i) => {
    const isTarget = line && (c.line === line || (c.line <= line && (d.chunks[i + 1]?.line ?? Infinity) > line));
    const el = h("section", { class: `chunk md${isTarget ? " target" : ""}`, id: `L${c.line}` });
    el.append(renderMarkdown(c.text, { mark: isTarget ? mark : null }));
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
  if (!idx) {
    list.replaceChildren(h("li", {}, "No index packaged."));
    return;
  }
  const f = $("recipe-filter").value.trim().toLowerCase();
  const items = idx.meta.recipes.filter((r) => !f || `${r.name} ${r.title} ${r.summary}`.toLowerCase().includes(f));
  list.replaceChildren(...items.map((r) => h("li", { tabindex: "0", onclick: () => go("doc", { path: r.path }),
    onkeydown: (e) => { if (e.key === "Enter") go("doc", { path: r.path }); } },
  h("h3", {}, r.title), h("p", {}, r.summary), h("span", { class: "kind" }, (r.applies_to || []).join(" · ")))));
}

// ---------------------------------------------------------------- optimizer

function refLink(ref) {
  return h("a", { href: `#doc?path=${encodeURIComponent(ref)}` }, "Read more in the corpus");
}

function runOptimize() {
  const text = $("opt-input").value;
  if (!text.trim()) return;
  let rep;
  try {
    rep = optimize(text);
  } catch (err) {
    $("opt-out").replaceChildren(h("p", { class: "status error" }, `The optimizer could not read this input: ${err.message}`));
    return;
  }
  $("opt-out").replaceChildren(renderReport(rep, { refLink,
    extra: h("button", { type: "button", class: "small", onclick: () => { $("lint-input").value = text; go("lint"); runLint(); } }, "Lint this") }));
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
  out.replaceChildren(
    h("div", { class: "summary" }, diags.length ? ["error", "warning", "info", "hint"].map((sev) => {
      const n = diags.filter((d) => d.severity === sev).length;
      return n ? h("span", { class: `chip sev-${sev}` }, `${n} ${sev}`) : null;
    }) : h("span", { class: "chip ok" }, "no problems found")),
    ...diags.map((d) => h("div", { class: `diag sev-${d.severity}` },
      h("div", { class: "head" }, `${d.line + 1}:${d.column + 1} ${d.severity.toUpperCase()} · ${d.code}`),
      h("p", {}, d.message, d.fix ? [" ", h("code", {}, d.fix)] : null))),
    symbols.length ? [h("h2", {}, "Outline"), outline(symbols)] : null);
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
  try {
    const { settings } = await chrome.storage.local.get("settings");
    if (settings) Object.assign(state.settings, settings);
  } catch { /* defaults */ }
  if (state.settings.semantic) state.mode = "hybrid";
}

async function saveSettings() {
  try {
    await chrome.storage.local.set({ settings: state.settings });
  } catch { /* ignore */ }
}

function originPattern(host) {
  const u = new URL(host);
  return `${u.protocol}//${u.hostname}/*`;
}

async function renderAbout() {
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
  $("ollama-host").value = state.settings.host;
  $("ollama-status").textContent = state.settings.semantic ? `On — using ${state.settings.host}` : "Off — keyword search only.";
}

function showOllamaHelp(show) {
  const box = $("ollama-help");
  box.hidden = !show;
  if (!show) return;
  const id = chrome.runtime.id;
  const mac = `launchctl setenv OLLAMA_ORIGINS "chrome-extension://${id}"`;
  const linux = `sudo systemctl edit ollama   # add: Environment="OLLAMA_ORIGINS=chrome-extension://${id}"`;
  box.replaceChildren(
    h("p", {}, "Ollama only accepts requests from origins it trusts. Allow this extension, then restart Ollama:"),
    h("div", { class: "row" }, h("code", {}, mac), copyButton(() => mac)),
    h("div", { class: "row" }, h("code", {}, linux), copyButton(() => linux)),
    h("p", { class: "kind" }, "On Windows set the OLLAMA_ORIGINS user environment variable to the same value. Then click Enable and test again."));
}

async function enableOllama() {
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
  if (!granted) {
    status.textContent = "Permission to reach that address was not granted.";
    status.classList.add("error");
    return;
  }
  const idx = await ensureIndex();
  const model = (idx && idx.meta.vectors && idx.meta.vectors.model) || "nomic-embed-text";
  status.textContent = `Testing ${host} with ${model}…`;
  try {
    const v = await embedQuery("ping", { host, model });
    if (idx && idx.dim && v.length !== idx.dim) throw new EmbedError(`the model returned ${v.length} dimensions but the index has ${idx.dim}; pull ${model}`);
    state.settings = { semantic: true, host };
    await saveSettings();
    state.mode = "hybrid";
    showOllamaHelp(false);
    status.textContent = `On — ${host} answered with ${v.length}-dimension ${model} embeddings. Hybrid is now the default search mode.`;
  } catch (err) {
    status.textContent = err.message;
    status.classList.add("error");
    showOllamaHelp(/403/.test(err.message));
  }
}

async function disableOllama() {
  state.settings.semantic = false;
  state.mode = "keyword";
  await saveSettings();
  $("ollama-status").textContent = "Off — keyword search only.";
}

// ---------------------------------------------------------------- startup

async function consumePending() {
  try {
    const { appPending } = await chrome.storage.session.get("appPending");
    if (!appPending) return false;
    await chrome.storage.session.remove("appPending");
    if (Date.now() - appPending.ts > 60_000 || !appPending.text) return false;
    if (appPending.tab === "lint") {
      $("lint-input").value = appPending.text;
      go("lint");
      runLint();
    } else if (appPending.tab === "optimize") {
      $("opt-input").value = appPending.text;
      go("optimize");
      runOptimize();
    } else {
      go("search", { q: appPending.text.slice(0, 500) });
    }
    return true;
  } catch {
    return false;
  }
}

function wire() {
  $("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    go("search", { q: $("q").value, kind: state.kind, source: state.source, mode: $("mode").value });
  });
  $("mode").addEventListener("change", () => { state.mode = $("mode").value; if ($("q").value.trim()) runSearch($("q").value); });
  $("facet-filter").addEventListener("input", () => renderFacets());
  $("clear-scope").addEventListener("click", () => go("search", { q: $("q").value, kind: state.kind, mode: state.mode }));
  $("doc-back").addEventListener("click", () => { if (history.length > 1) history.back(); else location.hash = state.lastSearchHash; });
  $("recipe-filter").addEventListener("input", () => renderRecipes());
  $("op-filter").addEventListener("input", () => renderOperators());
  $("opt-run").addEventListener("click", runOptimize);
  $("opt-example").addEventListener("click", () => { $("opt-input").value = EXAMPLE_LOG; runOptimize(); });
  $("lint-run").addEventListener("click", runLint);
  $("lint-to-opt").addEventListener("click", () => { $("opt-input").value = $("lint-input").value; go("optimize"); runOptimize(); });
  $("ollama-enable").addEventListener("click", enableOllama);
  $("ollama-disable").addEventListener("click", disableOllama);
  for (const [id, fn] of [["opt-input", runOptimize], ["lint-input", runLint]]) {
    $(id).addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) fn(); });
  }
  document.addEventListener("keydown", (e) => {
    if ($("tab-search").hidden) return;
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (e.key === "/" && !typing) { e.preventDefault(); $("q").focus(); $("q").select(); }
    else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && state.hits.length && document.activeElement !== $("facet-filter")) {
      e.preventDefault();
      select(Math.max(0, Math.min(state.hits.length - 1, state.selected + (e.key === "ArrowDown" ? 1 : -1))));
    } else if (e.key === "Enter" && !typing && state.hits[state.selected]) {
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
}

main();
