// Batch runner for tests/test_js_parity.py: reads a JSON array of input texts on stdin and writes a
// JSON array of { apply, read_only } results (same shape as the Python to_dict) to stdout.
import { optimize, toDict } from "../lib/optimize.js";

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => { raw += c; });
process.stdin.on("end", () => {
  const texts = JSON.parse(raw);
  const out = texts.map((t) => ({ apply: toDict(optimize(t)), read_only: toDict(optimize(t, { apply: false })) }));
  process.stdout.write(JSON.stringify(out));
});
