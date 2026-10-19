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


def test_side_width_fits_then_caps():
    from mdbx.tui import SIDE_CHROME, SIDE_MIN, side_width

    assert side_width(10, 200) == SIDE_MIN  # short labels keep the minimum
    assert side_width(50, 200) == 50 + SIDE_CHROME  # wide terminal: fit the longest label
    assert side_width(50, 80) == 36  # narrow terminal: capped at 45%


@pytest.mark.asyncio
async def test_tui_facet_sidebar_fits_long_names(tmp_path):
    root = make_corpus(tmp_path)
    long = "mongodb-atlas-slow-query-and-advisor-automation"
    d = root / "llms" / f"{long}.llms"
    d.mkdir(parents=True)
    (d / "llms.txt").write_text("# Slow query automation\n\nPerformance Advisor and slow query log automation.\n")
    db = tmp_path / "t.sqlite"
    con = index.connect(db)
    index.build_keyword(con, root)
    con.close()
    app = MdbxApp(db)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause()
        side = app.query_one("#side")
        assert side.size.width >= len(long) + len("  (1)") + 2  # the label fits on one line
        facets = app.query_one("#facets")
        assert all(o.prompt.no_wrap for o in facets._options)
    narrow = MdbxApp(db)
    async with narrow.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        from mdbx.tui import SIDE_CHROME

        width = narrow.query_one("#side").size.width
        assert width <= 36  # results keep most of a narrow terminal
        labels = [o.prompt for o in narrow.query_one("#facets")._options]
        target = narrow._facet_width  # usable label width the sidebar was sized for
        assert target is not None and target <= width - SIDE_CHROME + 1
        assert all(t.cell_len <= target for t in labels)  # cut with "…", never wrapped
        assert any(t.plain.endswith("…  (1)") for t in labels)
