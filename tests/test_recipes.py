from pathlib import Path

import pytest

from mdbx import cli, corpus, index, recipes

RECIPE = """---
name: shard-a-collection
title: Shard a collection
summary: Pick a shard key and shard a live collection.
applies_to: [atlas, self-managed]
sources: [skills/mongodb-expert/SKILL.md]
---
# Shard a collection
## Steps
1. Run sh.shardCollection("mydb.orders", { customerId: "hashed" }).
"""


@pytest.fixture()
def root(tmp_path, monkeypatch):
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "shard-a-collection.md").write_text(RECIPE)
    (tmp_path / "recipes" / "atlas-private-link.md").write_text(
        RECIPE.replace("shard-a-collection", "atlas-private-link").replace("Shard a collection", "Add Atlas Private Link").replace('sh.shardCollection("mydb.orders", { customerId: "hashed" })', 'atlas networking privateLink create')
    )
    monkeypatch.setenv("MDBX_CORPUS", str(tmp_path))
    return tmp_path


def test_classify_recipe():
    assert corpus.classify(Path("recipes/shard-a-collection.md")) == ("recipe", "shard-a-collection")


def test_frontmatter_and_load(root):
    items = recipes.load(root)
    assert [r.name for r in items] == ["atlas-private-link", "shard-a-collection"]
    r = items[1]
    assert r.applies_to == ["atlas", "self-managed"] and r.sources == ["skills/mongodb-expert/SKILL.md"]
    assert "sh.shardCollection" in r.text


def test_find_exact_and_fuzzy(root):
    assert [r.name for r in recipes.find("shard-a-collection", root)] == ["shard-a-collection"]
    assert [r.name for r in recipes.find("private link", root)] == ["atlas-private-link"]
    assert recipes.find("nonexistent thing", root) == []


def test_recipes_are_searchable_by_kind(root, tmp_path):
    from contextlib import closing

    from mdbx import search

    skill = root / 'skills' / 'synthetic-kind' / 'SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('# Synthetic skill\nshardCollection hashed\n')
    with closing(index.connect(tmp_path / "r.sqlite")) as con:
        index.build_keyword(con, root)
        assert {'recipe','skill'} <= {h.kind for h in search.keyword(con,'shardCollection hashed')}
        hits = search.keyword(con, "shardCollection hashed", kind="recipe")
        assert hits and all(h.kind == 'recipe' for h in hits) and hits[0].source == 'shard-a-collection'


def test_cli_recipes(root, capsys):
    assert cli.main(["recipes"]) == 0
    out = capsys.readouterr().out
    assert "shard-a-collection" in out and "[atlas/self-managed]" in out
    assert cli.main(["recipes", "private"]) == 0
    filtered = capsys.readouterr().out
    assert "atlas-private-link" in filtered and "shard-a-collection" not in filtered
    assert cli.main(["recipe", "shard", "a", "collection"]) == 0
    assert "# Shard a collection" in capsys.readouterr().out
    assert cli.main(["recipe", "zzz"]) == 1


def test_mcp_recipe_tools(root):
    pytest.importorskip("mcp")
    from mdbx import mcp_server as m

    assert {r["name"] for r in m.mdb_recipes()} == {"atlas-private-link", "shard-a-collection"}
    assert [r["name"] for r in m.mdb_recipes("link")] == ["atlas-private-link"]
    selected = m.mdb_recipe("shard a collection")
    assert "sh.shardCollection" in selected and "privateLink create" not in selected
    selected = m.mdb_recipe("atlas private link")
    assert "privateLink create" in selected and "sh.shardCollection" not in selected
    with pytest.raises(ValueError):
        m.mdb_recipe("nope")


def test_review_recipe_paths_are_confined_and_directories_skipped(root):
    (root/'recipes'/'extra.md').mkdir()
    outside = root.parent/'outside.md'
    outside.write_text('synthetic outside content')
    (root/'recipes'/'escape.md').symlink_to(outside)
    assert {r.path for r in recipes.load(root)} == {'recipes/atlas-private-link.md','recipes/shard-a-collection.md'}
    item = recipes.Recipe('escape','Escape','',path='recipes/escape.md',root=root)
    with pytest.raises(ValueError):
        _ = item.text
