import { test } from "node:test";
import assert from "node:assert/strict";
import { pageFixture, deferred } from "./dom-fixture.mjs";

test("repeated copy feedback restores the original label and ignores stale writes", async () => {
  const timers = new Map(); let id = 0;
  const p = pageFixture("lib/ui.js", { globals: { setTimeout: fn => { timers.set(++id, fn); return id; }, clearTimeout: key => timers.delete(key) } });
  const button = p.document.createElement("button"); button.textContent = "Copy citation";
  await p.copyText("first", button); assert.equal(button.textContent, "Copied");
  await p.copyText("second", button); assert.equal(timers.size, 1);
  for (const fn of timers.values()) fn(); assert.equal(button.textContent, "Copy citation");
  const first = deferred(), second = deferred(); let calls = 0;
  p.context.navigator.clipboard.writeText = () => (++calls === 1 ? first.promise : second.promise);
  const a = p.copyText("first", button), b = p.copyText("second", button);
  second.resolve(); await b; first.reject(Error("synthetic failure")); await a;
  assert.equal(button.textContent, "Copied");
});

test("Unicode query words highlight whole non-Latin words", () => {
  const p = pageFixture("lib/ui.js");
  const fragment = p.renderMarkdown("Проверка индексов 数据库 검색어", { mark: p.markFor("индексы 数据库 검색어") });
  assert.deepEqual(fragment.querySelectorAll("mark").map(n => n.textContent), ["индексов", "数据库", "검색어"]);
  assert.equal(fragment.textContent, "Проверка индексов 数据库 검색어");
});

test("list type changes and ordered start numbers preserve structure", () => {
  const p = pageFixture("lib/ui.js");
  const fragment = p.renderMarkdown("3. three\n4. four\n- bullet\n7. seven");
  assert.deepEqual(fragment.children.map(n => n.tagName), ["OL", "UL", "OL"]);
  assert.equal(fragment.children[0].getAttribute("start"), "3");
  assert.equal(fragment.children[2].getAttribute("start"), "7");
  assert.deepEqual(fragment.children.map(list => list.children.map(n => [n.tagName, n.textContent])), [[["LI", "three"], ["LI", "four"]], [["LI", "bullet"]], [["LI", "seven"]]]);
});

test("unmatched opening brackets do not rescan every remaining suffix", () => {
  const p = pageFixture("lib/ui.js");
  const source = "[".repeat(100000);
  const result = p.renderMarkdown(source);
  assert.equal(result.textContent, source);
});
