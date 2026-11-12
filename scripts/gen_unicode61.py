"""Regenerate the Unicode61 lookup using synthetic single-scalar in-memory SQLite rows only."""
from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import sqlite3
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENIZER = "unicode61 remove_diacritics 2 tokenchars '_'"
BATCH = 4096

def derive():
    ranges, folds, ignorable = [], {}, []
    active_start = active_end = None
    started = time.monotonic()
    scanned = 0
    with closing(sqlite3.connect(":memory:")) as con:
        for lower in range(0, 0x110000, BATCH):
            values = [code for code in range(lower, min(lower+BATCH, 0x110000)) if not 0xD800 <= code <= 0xDFFF]
            con.execute(f'CREATE VIRTUAL TABLE f USING fts5(text, tokenize="{TOKENIZER}")')
            con.execute("CREATE VIRTUAL TABLE v USING fts5vocab(f, 'instance')")
            con.executemany("INSERT INTO f(rowid,text) VALUES (?,?)",
                            ((rowid, text) for code in values for rowid, text in ((code*2+1, "a"+chr(code)+"z"), (code*2+2, chr(code)))))
            observed = {}
            for doc, term in con.execute("SELECT doc,term FROM v ORDER BY doc,offset"):
                observed.setdefault(doc, []).append(term)
            for code in values:
                terms = observed.get(code*2+1, [])
                standalone = observed.get(code*2+2, [])
                if terms == ["a", "z"]:
                    is_token = False
                elif len(terms) == 1 and terms[0].startswith("a") and terms[0].endswith("z"):
                    middle = terms[0][1:-1]
                    if not middle:
                        ignorable.append(code)
                        is_token = False
                    else:
                        assert len(middle) == 1, (code, terms)
                        is_token = True
                        if middle != chr(code):
                            folds[code] = ord(middle)
                else:
                    raise AssertionError((code, terms))
                assert standalone == ([middle] if is_token else []), (code, terms, standalone)
                if is_token:
                    if active_end is not None and code == active_end+1:
                        active_end = code
                    else:
                        if active_start is not None:
                            ranges.append([active_start, active_end])
                        active_start = active_end = code
                elif active_start is not None:
                    ranges.append([active_start, active_end])
                    active_start = active_end = None
            scanned += len(values)
            con.execute("DROP TABLE v")
            con.execute("DROP TABLE f")
            if lower % (BATCH*32) == 0:
                print(json.dumps({"scanned": scanned, "seconds": round(time.monotonic()-started, 2)}), flush=True)
    if active_start is not None:
        ranges.append([active_start, active_end])
    result = {"sqlite_version": sqlite3.sqlite_version, "tokenizer": TOKENIZER, "scanned_scalars": scanned,
              "standalone_verified": True, "token_ranges": ranges, "folds": folds, "ignorable": ignorable}
    return result

PY_BODY = '\ndef _token_character(code: int) -> bool:\n    position = bisect_right(_TOKEN_STARTS, code) - 1\n    return position >= 0 and code <= TOKEN_RANGES[position][1]\n\n\ndef raw_tokens(text: str) -> list[str]:\n    """Fold and split exactly as the recorded Unicode61 tokenizer, without Unicode normalization."""\n    output, current = [], []\n    for character in text:\n        code = ord(character)\n        if _token_character(code):\n            current.append(chr(FOLDS.get(code, code)))\n        elif current and code in IGNORABLE:\n            continue\n        elif current:\n            output.append("".join(current))\n            current = []\n    if current:\n        output.append("".join(current))\n    return output\n'
JS_BODY = '\nfunction tokenCharacter(code) {\n  let lo = 0, hi = TOKEN_RANGES.length;\n  while (lo < hi) {\n    const mid = (lo + hi) >>> 1;\n    if (TOKEN_RANGES[mid][0] <= code) lo = mid + 1; else hi = mid;\n  }\n  return lo > 0 && code <= TOKEN_RANGES[lo - 1][1];\n}\n\n/** Unicode61-folded tokens and source UTF-16 spans. Ignored leading marks do not start tokens. */\nexport function rawTokenSpans(text) {\n  const output = [];\n  let current = "", start = 0, offset = 0;\n  for (const character of text) {\n    const code = character.codePointAt(0);\n    if (tokenCharacter(code)) {\n      if (!current) start = offset;\n      current += String.fromCodePoint(FOLDS.get(code) ?? code);\n    } else if (!(current && IGNORABLE.has(code)) && current) {\n      output.push([current, start, offset]);\n      current = "";\n    }\n    offset += character.length;\n  }\n  if (current) output.push([current, start, offset]);\n  return output;\n}\n'


def render(data, generator_hash):
    proof = {key: data[key] for key in ("sqlite_version", "tokenizer", "scanned_scalars", "standalone_verified")}
    proof["generator_sha256"] = generator_hash
    folds = {int(key): value for key, value in data["folds"].items()}
    py = '"""Generated Unicode61 classification and simple folds. Regenerate with scripts/gen_unicode61.py."""\n'
    py += "from bisect import bisect_right\n\n"
    py += "UNICODE61_PROVENANCE = " + pprint.pformat(proof, width=100) + "\n"
    py += "TOKEN_RANGES = " + pprint.pformat(tuple(map(tuple, data["token_ranges"])), width=100) + "\n"
    py += "_TOKEN_STARTS = tuple(start for start, _ in TOKEN_RANGES)\n"
    py += "FOLDS = " + pprint.pformat(folds, width=100) + "\n"
    py += "IGNORABLE = frozenset(" + pprint.pformat(tuple(data["ignorable"]), width=100) + ")\n"
    py += PY_BODY
    js = "// Generated Unicode61 classification and simple folds. Regenerate with scripts/gen_unicode61.py.\n"
    js += "export const UNICODE61_PROVENANCE = " + json.dumps(proof, indent=2) + ";\n"
    js += "const TOKEN_RANGES = " + json.dumps(data["token_ranges"], separators=(",", ":")) + ";\n"
    js += "const FOLDS = new Map(" + json.dumps(list(folds.items()), separators=(",", ":")) + ");\n"
    js += "const IGNORABLE = new Set(" + json.dumps(data["ignorable"]) + ");\n"
    js += JS_BODY
    return {"mdbx/unicode61.py": py, "editors/chrome/lib/unicode61.js": js}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = derive()
    generated = render(data, hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    stale = []
    for relative, content in generated.items():
        destination = ROOT / relative
        if args.check:
            if not destination.is_file() or destination.read_text(encoding="utf-8") != content:
                stale.append(relative)
        else:
            destination.write_text(content, encoding="utf-8")
    if stale:
        print("stale Unicode61 tables: " + ", ".join(stale))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
