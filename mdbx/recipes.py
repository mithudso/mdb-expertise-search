"""recipes — curated step-by-step runbooks stored in ``corpus/recipes/*.md``.

Each recipe starts with a small frontmatter block (name, title, summary, applies_to, sources).
Recipes are also indexed like any other corpus file (kind ``recipe``), so ``mdbx search`` finds them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import index as idx

_FM = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


@dataclass
class Recipe:
    name: str
    title: str
    summary: str
    applies_to: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    path: str = ""  # corpus-relative

    @property
    def text(self) -> str:
        return (idx.default_corpus() / self.path).read_text(encoding="utf-8", errors="replace")


def _list_value(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [p.strip().strip("'\"") for p in raw.split(",") if p.strip()]


def parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def load(root: Path | None = None) -> list[Recipe]:
    root = root or idx.default_corpus()
    recipes: list[Recipe] = []
    for p in sorted((root / "recipes").glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        fm = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        recipes.append(
            Recipe(
                name=fm.get("name") or p.stem,
                title=fm.get("title") or p.stem.replace("-", " ").title(),
                summary=fm.get("summary", ""),
                applies_to=_list_value(fm.get("applies_to", "")),
                sources=_list_value(fm.get("sources", "")),
                path=str(p.relative_to(root)),
            )
        )
    return recipes


def find(name: str, root: Path | None = None) -> list[Recipe]:
    """Exact name match first, otherwise every recipe whose name/title contains ``name``."""
    needle = name.lower().strip()
    items = load(root)
    exact = [r for r in items if r.name.lower() == needle]
    if exact:
        return exact
    parts = needle.replace("-", " ").split()
    return [r for r in items if all(p in (r.name + " " + r.title).lower().replace("-", " ") for p in parts)]
