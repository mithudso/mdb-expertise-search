import pytest

pytest.importorskip("textual")

from mdbx import index
from mdbx.tui import MdbxApp

from .test_core import make_corpus


@pytest.mark.asyncio
async def test_tui_keyword_search(tmp_path):
    db = tmp_path / "t.sqlite"
    con = index.connect(db)
    index.build_keyword(con, make_corpus(tmp_path))
    con.close()
    app = MdbxApp(db)
    async with app.run_test() as pilot:
        app.mode = 1  # keyword, no Ollama needed
        app.query_one("#q").value = "shard key"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.hits and app.hits[0].source == "mongodb-expert"


@pytest.mark.asyncio
async def test_tui_recipes_shortcut(tmp_path, monkeypatch):
    root = make_corpus(tmp_path)
    (root / "recipes").mkdir()
    (root / "recipes" / "shard-a-collection.md").write_text(
        "---\nname: shard-a-collection\ntitle: Shard a collection\nsummary: s\napplies_to: [atlas]\nsources: []\n---\n# Shard a collection\n"
    )
    monkeypatch.setenv("MDBX_CORPUS", str(root))
    db = tmp_path / "t.sqlite"
    con = index.connect(db)
    index.build_keyword(con, root)
    con.close()
    app = MdbxApp(db)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert [h.source for h in app.hits] == ["shard-a-collection"] and app.hits[0].kind == "recipe"
