// Minimal synthetic DOM for executing the maintained page sources. No browser, profiles or network.
import vm from "node:vm";
import { readFileSync } from "node:fs";
import * as capture from "../lib/capture.js";
import { EmbedError, STOPWORDS, snippet } from "../lib/textsearch.js";
import { docFor, ESR_DOC } from "../lib/docs.js";
import { scanRatio, severityCounts, kindLabel, toMarkdown } from "../lib/report.js";

export const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
export async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }

class SyntheticNode {
  constructor(tag = "", text = "") {
    this.tagName = tag.toUpperCase(); this.nodes = []; this.attrs = {}; this.listeners = {};
    this._text = text; this.hidden = false; this.value = ""; this.dataset = {};
    this.classList = {
      contains: name => this.className.split(/\s+/).includes(name),
      add: name => { this.className = [...new Set([...this.className.split(/\s+/).filter(Boolean), name])].join(" "); },
      remove: name => { this.className = this.className.split(/\s+/).filter(x => x !== name).join(" "); },
      toggle: (name, on) => { const yes = on ?? !this.classList.contains(name); this.classList[yes ? "add" : "remove"](name); },
    };
  }
  get className() { return this.attrs.class || ""; }
  set className(value) { this.attrs.class = value; }
  get children() { return this.nodes.filter(n => n.tagName); }
  get textContent() { return this._text + this.nodes.map(n => n.textContent).join(""); }
  set textContent(text) { this.nodes = []; this._text = String(text); }
  append(...nodes) { for (const n of nodes.flat(Infinity)) { if (n instanceof SyntheticNode && n.fragment) this.append(...n.nodes); else this.nodes.push(n instanceof SyntheticNode ? n : new SyntheticNode("", String(n))); } }
  replaceChildren(...nodes) { this.nodes = []; this._text = ""; this.append(...nodes); }
  setAttribute(key, value) { this.attrs[key] = String(value); if (key.startsWith("data-")) this.dataset[key.slice(5)] = String(value); }
  getAttribute(key) { return this.attrs[key] ?? null; }
  addEventListener(type, listener) { (this.listeners[type] ??= []).push(listener); }
  async emit(type, event = {}) { event.preventDefault ??= () => { event.defaultPrevented = true; }; event.target ??= this; for (const fn of this.listeners[type] || []) await fn(event); return event; }
  focus() { this.ownerDocument.activeElement = this; }
  select() {}
  scrollIntoView() {}
  querySelectorAll(selector) {
    const matches = n => selector.startsWith(".") ? n.classList.contains(selector.slice(1)) : n.tagName === selector.toUpperCase();
    const out = [];
    const visit = n => { for (const c of n.nodes) { if (matches(c)) out.push(c); visit(c); } };
    visit(this); return out;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

export function sessionStore(initial = {}) {
  const values = structuredClone(initial);
  return { values,
    async get(key) { return structuredClone(key === null ? values : { [key]: values[key] }); },
    async set(items) { Object.assign(values, structuredClone(items)); },
    async remove(keys) { for (const key of Array.isArray(keys) ? keys : [keys]) delete values[key]; },
  };
}

export function pageFixture(name = "app.js", options = {}) {
  const document = new SyntheticNode("document");
  document.createElement = tag => { const node = new SyntheticNode(tag); node.ownerDocument = document; return node; };
  document.createTextNode = text => new SyntheticNode("", String(text));
  document.createDocumentFragment = () => { const node = new SyntheticNode(); node.fragment = true; return node; };
  document.body = document.createElement("body");
  const elements = new Map();
  const html = readFileSync(new URL(name === "popup.js" ? "../popup.html" : "../app.html", import.meta.url), "utf8");
  for (const match of html.matchAll(/<([\w-]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const node = document.createElement(match[1]); node.setAttribute("id", match[2]); elements.set(match[2], node);
  }
  const tabs = [];
  for (const match of html.matchAll(/<a\b([^>]*)data-tab="([^"]+)"([^>]*)>/g)) {
    const node = document.createElement("a"); node.dataset.tab = match[2]; tabs.push(node);
  }
  document.getElementById = id => { if (!elements.has(id)) throw Error(`missing fixture id ${id}`); return elements.get(id); };
  document.querySelectorAll = selector => selector === ".tabs a" ? tabs : [];
  const opened = [], windowListeners = {};
  const chrome = { runtime: { getURL: value => `chrome-extension://synthetic/${value}`, id: "synthetic", getManifest: () => ({ version: "test" }) },
    storage: { session: sessionStore(), local: sessionStore() }, permissions: { request: async () => true },
    tabs: { query: async () => [], create: async value => { opened.push(value); return {}; } },
  };
  const deps = { getIndex: async () => null, embedQuery: async () => [1, 0], optimize: () => ({ inputQueries: 0 }),
    analyze: () => ({ diagnostics: [], symbols: [] }), diagnosticsToDicts: () => [], symbolsToDicts: () => [], ...options.deps };
  const location = { hash: options.hash ?? "#search" };
  const context = vm.createContext({ document, Node: SyntheticNode, chrome, location, history: { length: 1 },
    window: { addEventListener: (type, fn) => { windowListeners[type] = fn; }, close() {} },
    navigator: { clipboard: { writeText: async () => {} } }, performance, URLSearchParams, URL, console,
    setTimeout, clearTimeout, requestAnimationFrame: fn => fn(), EmbedError, STOPWORDS, snippet, docFor, ESR_DOC,
    scanRatio, severityCounts, kindLabel, toMarkdown, ...capture,
    OPERATORS: new Map(), ...Object.fromEntries(Object.keys(deps).map(key => [key, (...args) => deps[key](...args)])),
    fetch: () => { throw Error("network forbidden in synthetic DOM"); }, ...options.globals,
  });
  const readSource = file => readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
  const strip = source => source.replace(/^import .*;\r?\n/gm, "").replace(/^export /gm, "").replace(/^main\(\);\s*$/m, "");
  vm.runInContext(strip(options.uiSource ?? readSource("lib/ui.js")), context, { filename: "lib/ui.js" });
  if (name !== "lib/ui.js") vm.runInContext(strip(options.source ?? readSource(name)), context, { filename: name });
  const names = name === "app.js" ? ["state", "route", "go", "wire", "runSearch", "showDocument", "enableOllama", "disableOllama", "consumePending", "loadSettings"]
    : name === "popup.js" ? ["run", "renderCorpusHits", "readSelection"] : ["copyText", "markFor", "renderMarkdown"];
  const api = vm.runInContext(`({${names.join(",")}})`, context);
  return { ...api, context, deps, chrome, document, location, opened, tabs, $: id => document.getElementById(id) };
}

export function backgroundFixture() {
  const handlers = {}, opened = [], session = sessionStore();
  const chrome = { runtime: { getURL: value => `chrome-extension://synthetic/${value}`, onInstalled: { addListener() {} } },
    contextMenus: { onClicked: { addListener: fn => { handlers.click = fn; } } },
    omnibox: { setDefaultSuggestion() {}, onInputEntered: { addListener: fn => { handlers.omnibox = fn; } } },
    storage: { session }, tabs: { create: async options => { opened.push(options); }, update: async options => { opened.push(options); } } };
  const context = vm.createContext({ chrome, ...capture, startAutoUpdate() {} });
  const source = readFileSync(new URL("../background.js", import.meta.url), "utf8").replace(/^import .*;\r?\n/gm, "");
  vm.runInContext(source, context, { filename: "background.js" });
  return { chrome, handlers, opened, session };
}
