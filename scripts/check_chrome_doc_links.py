#!/usr/bin/env python3
"""Check that every MongoDB docs URL in editors/chrome/lib/docs.js resolves (HTTP 200 after redirects).

Network-dependent, so it is a manual / release check, not a CI gate:

    python scripts/check_chrome_doc_links.py
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "editors" / "chrome" / "lib" / "docs.js").read_text(encoding="utf-8")


def urls() -> list[str]:
    literal = r"""(["'`])((?:\\.|(?!\1)[^\\])*)\1"""
    base_match = re.search(r"const\s+M\s*=\s*" + literal, SRC)
    if base_match is None:
        raise ValueError("docs URL base constant is missing")
    base = base_match.group(2)
    if "${" in base:
        raise ValueError("dynamic documentation URL base cannot be checked")
    found = set()
    for match in re.finditer(r"\bM\s*\+\s*", SRC):
        position = match.end()
        fragments = []
        while True:
            piece = re.match(literal, SRC[position:])
            if piece is None:
                raise ValueError("documentation URL contains a nonliteral fragment")
            fragments.append(piece.group(2))
            position += piece.end()
            following = re.match(r"\s*\+\s*", SRC[position:])
            if following is None:
                break
            position += following.end()
        found.add(base + "".join(fragments))
    found |= {match.group(2) for match in re.finditer(literal, SRC) if match.group(2).startswith("https://")} - {base}
    if any("${" in url for url in found):
        raise ValueError("dynamic documentation URLs cannot be checked")
    return sorted(found)


def main() -> int:
    bad = []
    for u in urls():
        try:
            req = urllib.request.Request(u, method="GET", headers={"User-Agent": "mdbx-doc-link-check"})
            with urllib.request.urlopen(req, timeout=20) as r:
                status = r.status
        except Exception as exc:  # noqa: BLE001 — report every failure kind the same way
            status = getattr(exc, "code", str(exc))
        print(f"{status}  {u}")
        if status != 200:
            bad.append(u)
    print(f"{len(bad)} broken link(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
