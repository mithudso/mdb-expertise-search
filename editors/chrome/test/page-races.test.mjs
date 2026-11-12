import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pageFixture, backgroundFixture, deferred, flush, sessionStore } from "./dom-fixture.mjs";
import { MAX_INPUT, saveHandoff, consumeHandoff, HANDOFF_PREFIX } from "../lib/capture.js";

function index() {
  return { n: 1, vectors: true, dim: 2, meta: { files: 1, vectors: { model: "synthetic" } }, facets: () => [],
    keyword: (q, _limit, opts = {}) => [{ path: "synthetic.md", source: opts.source || "test", kind: "doc", line: 1, heading: q, text: q, score: 1, via: "keyword" }],
    semanticVec: () => [], hybridVec: () => [], document: () => null };
}

test("new searches and empty submissions supersede pending embeddings and capture filters", async () => {
  const old = deferred(), idx = index(), calls = [];
  const p = pageFixture("app.js", { deps: { getIndex: async () => idx, embedQuery: () => old.promise } });
  p.state.settings.semantic = true; p.state.mode = "hybrid"; p.state.source = "old area";
  idx.hybridVec = (q, _v, _limit, opts) => { calls.push([q, opts.source]); return idx.keyword(q, 40, opts); };
  const first = p.runSearch("old query"); await flush();
  p.state.mode = "keyword"; p.state.source = "new area";
  await p.runSearch("new query");
  old.resolve([1, 0]); await first;
  assert.equal(p.state.q, "new query"); assert.match(p.$("results").textContent, /new query/);
  assert.doesNotMatch(p.$("results").textContent, /old query/); assert.deepEqual(calls, []);
  const pending = deferred(); p.deps.embedQuery = () => pending.promise;
  p.state.mode = "hybrid";
  const stale = p.runSearch("stale query"); await flush();
  await p.runSearch(""); pending.resolve([1, 0]); await stale;
  assert.equal(p.$("search-status").textContent, ""); assert.equal(p.state.hits.length, 0);
  assert.equal(p.state.q, ""); assert.equal(p.state.selected, -1); assert.equal(p.$("results").textContent, ""); assert.equal(p.$("detail").textContent, "");
  p.go("search", { q: "" }); assert.equal(new URLSearchParams(p.location.hash.split("?")[1]).get("q"), "");
});

test("every query validates embedding dimensions and falls back to keyword search", async () => {
  const idx = index();
  const p = pageFixture("app.js", { deps: { getIndex: async () => idx, embedQuery: async () => [1] } });
  p.state.settings.semantic = true; p.state.mode = "hybrid";
  idx.hybridVec = () => { throw Error("invalid embedding reached ranking"); };
  await p.runSearch("synthetic query");
  assert.match(p.$("search-status").textContent, /embedding.*index.*keyword results/);
  assert.equal(p.state.hits.length, 1);
});

test("disable wins over a pending enable and reports persistence failure", async () => {
  const reply = deferred();
  const p = pageFixture("app.js", { deps: { getIndex: async () => index(), embedQuery: () => reply.promise } });
  p.$("ollama-host").value = "http://127.0.0.1:9";
  const enabling = p.enableOllama(); await flush();
  await p.disableOllama(); reply.resolve([1, 0]); await enabling;
  assert.equal(p.state.settings.semantic, false); assert.equal(p.state.mode, "keyword");
  assert.equal(p.chrome.storage.local.values.settings.semantic, false); assert.match(p.$("ollama-status").textContent, /^Off/);
  p.chrome.storage.local.set = async () => { throw Error("synthetic write failure"); };
  await p.disableOllama();
  assert.equal(p.state.settings.semantic, false); assert.match(p.$("ollama-status").textContent, /Saving failed.*reopening/);
});

test("failed document navigation removes prior document title and copy actions", async () => {
  const idx = index();
  idx.document = path => path === "exists.md" ? { source: "test", chunks: [{ text: "synthetic", line: 1 }] } : null;
  const p = pageFixture("app.js", { deps: { getIndex: async () => idx } });
  await p.showDocument("exists.md", 0, ""); assert.ok(p.$("doc-actions").children.length);
  await p.showDocument("missing.md", 0, "");
  assert.equal(p.$("doc-title").textContent, ""); assert.equal(p.$("doc-actions").children.length, 0);
});

test("mode selectors retain native arrow behavior and tabs implement arrow focus", async () => {
  const p = pageFixture("app.js"); p.wire(); p.state.hits = [{}];
  p.$("mode").focus();
  const event = await p.document.emit("keydown", { key: "ArrowDown" });
  assert.ok(!event.defaultPrevented);
  await p.tabs[0].emit("keydown", { key: "ArrowRight" });
  assert.equal(p.document.activeElement, p.tabs[1]); assert.equal(p.location.hash, "#recipes");
  const html = readFileSync(new URL("../app.html", import.meta.url), "utf8");
  for (const tab of ["search", "recipes", "optimize", "lint", "operators", "about"]) {
    assert.match(html, new RegExp(`id="nav-${tab}" aria-controls="tab-${tab}"`));
    assert.match(html, new RegExp(`role="tabpanel" aria-labelledby="nav-${tab}" id="tab-${tab}"`));
  }
  assert.match(html, /semantic and hybrid search send query text over HTTP/);
});

test("popup stale corpus completion cannot replace a report or empty and failed runs", async () => {
  const d = deferred(); let fail = false;
  const p = pageFixture("popup.js", { deps: { getIndex: () => d.promise, optimize: text => {
    if (fail) throw Error("synthetic parse failure");
    return text.startsWith("db.") ? { inputQueries: 1, inputKind: "mongosh", findings: [], applied: [], indexes: [], evidence: [], interpreted: null } : { inputQueries: 0 };
  } } });
  p.run("old selection"); await flush();
  p.run("db.c.find({})"); const report = p.$("result").textContent;
  d.resolve(index()); await flush(); assert.equal(p.$("result").textContent, report);
  for (const replacement of ["", "bad query"]) {
    const pending = deferred(); p.deps.getIndex = () => pending.promise;
    fail = false; p.run("old corpus selection"); await flush();
    fail = replacement !== ""; p.run(replacement);
    pending.resolve(index()); await flush();
    assert.ok(p.$("result").hidden); assert.equal(p.$("result").textContent, "");
  }
});

test("popup distinguishes failed and absent index and preserves Unicode navigation", async () => {
  const p = pageFixture("popup.js", { deps: { getIndex: async () => { throw Error("synthetic JSON error"); } } });
  await p.renderCorpusHits("synthetic"); const failure = p.$("result").textContent;
  assert.match(failure, /Could not load/);
  p.deps.getIndex = async () => null; await p.renderCorpusHits("synthetic");
  assert.notEqual(failure, p.$("result").textContent);
  p.deps.getIndex = async () => index();
  await p.renderCorpusHits("a".repeat(299) + "😀");
  await p.$("result").querySelector("button").emit("click");
  assert.equal(p.opened.length, 1); assert.match(p.opened[0].url, /app.html#search\?q=/);
  assert.equal(new URLSearchParams(p.opened[0].url.split("?")[1]).get("q"), "a".repeat(299));
  await p.renderCorpusHits("a😀"); await p.$("result").querySelector("button").emit("click");
  assert.equal(new URLSearchParams(p.opened.at(-1).url.split("?")[1]).get("q"), "a😀");
});

test("handoff keys retain each selection and remove only their own entry", async () => {
  const session = sessionStore({ [HANDOFF_PREFIX + "expired"]: { text: "old", ts: 1 } });
  const first = await saveHandoff(session, { text: "first", tab: "lint" }, 100000, "first");
  const second = await saveHandoff(session, { text: "second", tab: "lint" }, 100000, "second");
  assert.equal(session.values[HANDOFF_PREFIX + "expired"], undefined);
  assert.equal((await consumeHandoff(session, first, 100001)).text, "first");
  assert.equal((await consumeHandoff(session, second, 100001)).text, "second");
  assert.equal(await consumeHandoff(session, first, 100002), null);
});

test("app and popup consume only the identified synthetic destination", async () => {
  const p = pageFixture("app.js", { hash: "#lint?handoff=lint-id" });
  await saveHandoff(p.chrome.storage.session, { text: "synthetic lint input", tab: "lint" }, Date.now(), "lint-id");
  await saveHandoff(p.chrome.storage.session, { text: "other input", tab: "optimize" }, Date.now(), "other-id");
  assert.equal(await p.consumePending(), true); assert.equal(p.$("lint-input").value, "synthetic lint input");
  assert.ok(p.chrome.storage.session.values[HANDOFF_PREFIX + "other-id"]);
  const popup = pageFixture("popup.js", { hash: "#tab?handoff=popup-id" });
  await saveHandoff(popup.chrome.storage.session, { text: "synthetic popup input" }, Date.now(), "popup-id");
  assert.equal((await popup.readSelection()).text, "synthetic popup input");
});

test("search mode, filters and settings are snapshots of the submitted request", async () => {
  const embedding = deferred(), calls = [], idx = index();
  const p = pageFixture("app.js", { deps: { getIndex: async () => idx, embedQuery: (_q, opts) => { calls.push(opts.host); return embedding.promise; } } });
  idx.hybridVec = (q, _v, _limit, opts) => { calls.push(opts.source); return idx.keyword(q, 40, opts); };
  p.state.mode = "hybrid"; p.state.source = "original"; p.state.settings = { semantic: true, host: "http://localhost:9" };
  const searching = p.runSearch("synthetic"); await flush();
  p.state.mode = "keyword"; p.state.source = "changed"; p.state.settings.host = "http://localhost:10";
  embedding.resolve([1, 0]); await searching;
  assert.deepEqual(calls, ["http://localhost:9", "original"]);
  assert.equal(p.state.hits[0].source, "original");
});

test("late startup settings cannot undo a disable", async () => {
  const loading = deferred(), p = pageFixture("app.js");
  p.chrome.storage.local.get = () => loading.promise;
  const startup = p.loadSettings(); await p.disableOllama();
  loading.resolve({ settings: { semantic: true, host: "http://localhost:9" } }); await startup;
  assert.equal(p.state.settings.semantic, false); assert.equal(p.state.mode, "keyword");
});

test("background launches route simultaneous handoffs by their own identity", async () => {
  const b = backgroundFixture();
  await Promise.all([
    b.handlers.click({ menuItemId: "mql-lint-selection", selectionText: "first selection" }),
    b.handlers.click({ menuItemId: "mql-lint-selection", selectionText: "second selection" }),
    b.handlers.click({ menuItemId: "mql-optimize-selection", selectionText: "third selection" }),
  ]);
  const ids = b.opened.map(({ url }) => new URLSearchParams(url.split("?")[1]).get("handoff"));
  assert.equal(new Set(ids).size, 3);
  const consumed = [];
  for (const { url } of b.opened) {
    const destination = url.includes("popup.html") ? "popup.js" : "app.js";
    const page = pageFixture(destination, { hash: new URL(url).hash });
    page.chrome.storage.session = b.session;
    if (destination === "popup.js") {
      const payload = await page.readSelection(); consumed.push(payload.text);
      assert.equal(payload.text, "third selection"); assert.match(url, /popup.html#tab\?/);
    } else {
      assert.match(url, /app.html#lint\?/);
      const id = new URLSearchParams(new URL(url).hash.split("?")[1]).get("handoff");
      assert.equal(b.session.values[HANDOFF_PREFIX + id].tab, "lint");
      assert.equal(await page.consumePending(), true); consumed.push(page.$("lint-input").value);
    }
  }
  assert.deepEqual(new Set(consumed), new Set(["first selection", "second selection", "third selection"]));
  assert.deepEqual(Object.keys(b.session.values), []);
  await b.handlers.click({ menuItemId: "mdb-search-selection", selectionText: "a".repeat(499) + "😀" });
  assert.doesNotThrow(() => decodeURIComponent(b.opened.at(-1).url));
  assert.ok(b.opened.at(-1).url.includes("#search?q="));
  assert.equal(new URLSearchParams(b.opened.at(-1).url.split("?")[1]).get("q"), "a".repeat(499));
  await b.handlers.click({ menuItemId: "mdb-search-selection", selectionText: "a😀" });
  assert.equal(new URLSearchParams(b.opened.at(-1).url.split("?")[1]).get("q"), "a😀");
});

test("explicit empty route clears prior results before a pending index load", async () => {
  const loading = deferred();
  const p = pageFixture("app.js", { hash: "#search?q=", deps: { getIndex: () => loading.promise } });
  p.state.q = "prior"; p.state.hits = [{}]; p.$("results").textContent = "prior results";
  const routing = p.route(); await flush();
  assert.equal(p.state.q, ""); assert.equal(p.$("results").textContent, ""); assert.equal(p.state.selected, -1);
  loading.resolve(index()); await routing;
});

test("bounded handoff provenance reaches popup status and both app tools", async () => {
  const popup = pageFixture("popup.js", { hash: "#tab?handoff=bounded" });
  await saveHandoff(popup.chrome.storage.session, {text: "x".repeat(MAX_INPUT + 1)}, Date.now(), "bounded");
  const pending = await popup.readSelection(); assert.equal(pending.truncated, true);
  popup.run(pending.text, pending.from, pending.truncated); await flush();
  assert.match(popup.$("status").textContent, /first 200,000/);
  const last = await popup.readSelection(); assert.equal(last.truncated, true); assert.equal(last.text.length, MAX_INPUT);
  for (const tab of ["lint", "optimize"]) {
    const app = pageFixture("app.js", { hash: `#${tab}?handoff=bounded`, deps: { optimize: () => ({inputQueries:0,findings:[],applied:[]}) } });
    await saveHandoff(app.chrome.storage.session, {text: "x".repeat(MAX_INPUT + 1), tab}, Date.now(), "bounded");
    assert.equal(await app.consumePending(), true);
    assert.match(app.$(tab === "lint" ? "lint-out" : "opt-out").textContent, /first 200,000/);
  }
});

test("document rendering carries fence context across unchanged corpus chunks", async () => {
  const chunks = [{id:0,line:1,heading:"synthetic",text:"```js\nfirst"}, {id:1,line:3,heading:"synthetic",text:"second\n```\nAfter"}];
  const idx = index(); idx.document = () => ({path:"synthetic.md",source:"test",kind:"doc",chunks});
  const app = pageFixture("app.js", {deps:{getIndex:async()=>idx}});
  await app.showDocument("synthetic.md", 3, "second");
  assert.deepEqual(app.$("doc").querySelectorAll("pre").map(n=>n.textContent), ["first", "second"]);
  assert.ok(app.$("doc").querySelectorAll("p").some(n=>n.textContent === "After"));
});
