// Parity: the JavaScript optimizer must produce exactly what the Python reference produces for every
// input in tests/fixtures/optimizer/ (goldens written by scripts/gen_optimizer_golden.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { formatReport, optimize, toDict } from "../lib/optimize.js";

const here = dirname(fileURLToPath(import.meta.url));
const FIX = join(here, "..", "..", "..", "tests", "fixtures", "optimizer");
const inputs = readdirSync(FIX).filter((f) => f.endsWith(".txt")).sort();

test("fixtures exist", () => {
  assert.ok(inputs.length >= 8, `expected fixtures in ${FIX}`);
});

for (const name of inputs) {
  const text = readFileSync(join(FIX, name), "utf8");
  const golden = JSON.parse(readFileSync(join(FIX, name.replace(/\.txt$/, ".golden.json")), "utf8"));

  test(`${name}: apply=true matches Python`, () => {
    assert.deepStrictEqual(toDict(optimize(text)), golden.apply);
  });

  test(`${name}: apply=false matches Python`, () => {
    assert.deepStrictEqual(toDict(optimize(text, { apply: false })), golden.read_only);
  });

  test(`${name}: text report matches Python`, () => {
    assert.equal(formatReport(optimize(text), name), golden.report);
  });
}
