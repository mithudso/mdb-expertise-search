// Batch runner for tests/test_js_lint_parity.py: reads { "texts": [...], "words": [...] } on stdin and
// writes { "lint": [...], "suggest": [...] } to stdout. lint[i] is { diagnostics, symbols } for texts[i]
// (same shape as scripts/gen_lint_golden.py lint_dict); suggest[i] is suggest(words[i]).
import { toDict } from "../lib/analyze.js";
import { suggest } from "../lib/operators.js";

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => { raw += c; });
process.stdin.on("end", () => {
  const { texts = [], words = [] } = JSON.parse(raw);
  const out = {
    lint: texts.map((t) => toDict(t)),
    suggest: words.map((w) => suggest(w)),
  };
  process.stdout.write(JSON.stringify(out));
});
