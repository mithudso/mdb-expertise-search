// Parity: the JavaScript analyzer must produce exactly what the Python reference produces for every
// input behind a tests/fixtures/lint/*.lint.json golden (written by scripts/gen_lint_golden.py), plus
// unit checks for the Python-compatible helpers (repr quoting, difflib suggestions).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { analyze, pyRepr, toDict } from "../lib/analyze.js";
import * as ops from "../lib/operators.js";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = join(here, "..", "..", "..");
const LINT = join(ROOT, "tests", "fixtures", "lint");
const goldens = readdirSync(LINT).filter((f) => f.endsWith(".lint.json")).sort();

test("goldens exist for every code", () => {
  assert.ok(goldens.length >= 15, `expected goldens in ${LINT}`);
  const codes = new Set();
  for (const g of goldens) {
    for (const d of JSON.parse(readFileSync(join(LINT, g), "utf8")).diagnostics) codes.add(d.code);
  }
  for (const c of ["syntax", "unknown-operator", "duplicate-key", "bad-argument", "perf", "misplaced-operator",
    "stage-position", "missing-field", "mixed-keys", "stage-shape", "removed-operator", "projection-mix",
    "update-shape", "unknown-field"]) {
    assert.ok(codes.has(c), `no golden exercises ${c}`);
  }
});

for (const name of goldens) {
  const golden = JSON.parse(readFileSync(join(LINT, name), "utf8"));
  const text = readFileSync(join(ROOT, golden.source), "utf8");

  test(`${name}: diagnostics match Python`, () => {
    assert.deepStrictEqual(toDict(text).diagnostics, golden.diagnostics);
  });

  test(`${name}: symbols match Python`, () => {
    assert.deepStrictEqual(toDict(text).symbols, golden.symbols);
  });
}

test("operator table loads", () => {
  assert.ok(ops.OPERATORS.size > 250);
  assert.equal(ops.get("$merge").arg, "string|object");
  assert.ok(ops.STAGES.has("$match") && ops.UPDATE_OPS.has("$set"));
  assert.deepEqual(ops.suggest("$grup"), ["$group"]);
  assert.deepEqual(ops.suggest("$zzzqqq"), []);
});

test("pyRepr matches Python repr()", () => {
  assert.equal(pyRepr("a"), "'a'");
  assert.equal(pyRepr("it's"), '"it\'s"');
  assert.equal(pyRepr('say "hi"'), "'say \"hi\"'");
  assert.equal(pyRepr("both ' and \""), "'both \\' and \"'");
  assert.equal(pyRepr("a\\b\n\t"), "'a\\\\b\\n\\t'");
  assert.equal(pyRepr("café"), "'café'");
  assert.equal(pyRepr("x y"), "'x\\xa0y'");
  assert.equal(pyRepr("x​y"), "'x\\u200by'");
  assert.equal(pyRepr("\x07\x7f"), "'\\x07\\x7f'");
});

test("analyze on empty and whitespace input is silent", () => {
  assert.deepEqual(analyze("").diagnostics, []);
  assert.deepEqual(analyze("  \n ").diagnostics, []);
});
