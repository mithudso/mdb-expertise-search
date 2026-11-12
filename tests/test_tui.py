import logging

import pytest

pytest.importorskip("textual")

from mdbx import index
from mdbx.tui import MdbxApp

from .test_core import make_corpus


@pytest.mark.asyncio
async def test_tui_keyword_search(tmp_path):
    db = tmp_path / "t.sqlite"
    con = index.connect(db)
    try:
        index.build_keyword(con, make_corpus(tmp_path))
    finally:
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
    try:
        index.build_keyword(con, root)
    finally:
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
    try:
        index.build_keyword(con, root)
    finally:
        con.close()
    app = MdbxApp(db)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause()
        side = app.query_one("#side")
        assert side.size.width >= len(long) + len("  (1)") + 2  # the label fits on one line
        facets = app.query_one("#facets")
        assert any(long in o.prompt.plain for o in facets._options)
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


@pytest.mark.asyncio
async def test_keyword_setup_failure_closes_connection(tmp_path, monkeypatch):
    from types import SimpleNamespace
    closed = []
    monkeypatch.setattr(index, "connect", lambda path: SimpleNamespace(close=lambda: closed.append(True)))
    def fail(path):
        raise OSError("synthetic corpus setup failure")
    monkeypatch.setitem(test_tui_keyword_search.__globals__, "make_corpus", fail)
    with pytest.raises(OSError, match="synthetic corpus setup failure"):
        await test_tui_keyword_search(tmp_path)
    assert closed == [True]


def test_review_facet_labels_use_cells_and_small_share():
    from mdbx.tui import facet_label, side_width
    label=facet_label('界'*10,1,16)
    assert label.cell_len<=16 and label.plain.endswith('…  (1)')
    assert side_width(50,40)<=18


@pytest.mark.asyncio
async def test_review_tui_selected_recipes_shutdown_and_old_search(tmp_path,monkeypatch,caplog):
    import asyncio
    import sqlite3
    from threading import Event

    from mdbx import tui as t
    caplog.set_level(logging.DEBUG, logger="mdbx.tui")
    root=make_corpus(tmp_path)
    (root/'recipes').mkdir()
    (root/'recipes'/'selected.md').write_text('# Selected\n')
    db=tmp_path/'ui.sqlite'
    con=index.connect(db)
    try:
        index.build_keyword(con,root)
    finally:
        con.close()
    other=tmp_path/'other'; other.mkdir()
    monkeypatch.setenv('MDBX_CORPUS',str(other))
    started,release=Event(),Event()
    def slow(*args,**kw):
        started.set()
        assert release.wait(5)
        raise t.embedmod.EmbedError('http://u:SYNTHETIC_SECRET@localhost:9')
    monkeypatch.setattr(t.srch,'search',slow)
    monkeypatch.setattr(t.srch,'keyword',lambda *a,**kw:[])
    app=MdbxApp(db)
    try:
        async with app.run_test(size=(40,24)) as pilot:
            await pilot.pause()
            assert app.query_one('#side').size.width<=18
            worker=app._search('old')
            assert await asyncio.to_thread(started.wait,5)
            recipes_worker = app.action_recipes()
            await recipes_worker.wait()
            assert [h.source for h in app.hits]==['selected']
            release.set()
            await worker.wait()
            assert [h.source for h in app.hits]==['selected']
            assert 'SYNTHETIC_SECRET' not in caplog.text
        with pytest.raises(sqlite3.ProgrammingError,match='closed'):
            app.con.execute('SELECT 1')
    finally:
        release.set()
        app.con.close()


@pytest.mark.asyncio
async def test_empty_query_clears_active_state_and_private_failure_is_opaque(tmp_path, monkeypatch, caplog):
    import sqlite3

    from mdbx import index
    from mdbx import tui as t
    caplog.set_level(logging.DEBUG, logger="mdbx.tui")
    db = tmp_path / "synthetic.sqlite"
    con = index.connect(db); con.close()
    def unavailable(*args, **kwargs):
        raise t.embedmod.EmbedError("SYNTHETIC_SECRET")
    def failed(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic sqlite failure")
    monkeypatch.setattr(t.srch, "search", unavailable)
    monkeypatch.setattr(t.srch, "keyword", failed)
    app = t.MdbxApp(db)
    async with app.run_test() as pilot:
        await pilot.pause()
        worker = app._search("synthetic")
        await worker.wait()
        assert "SYNTHETIC_SECRET" not in caplog.text
        assert "SYNTHETIC_SECRET" not in str(app.query_one("#status").render())
        assert "search failed" in caplog.text
        import asyncio
        from threading import Event

        from mdbx.search import Hit
        hit = Hit(1, "synthetic.md", "populated", "skill", "Heading", 1, "body", 1.0)
        app._render_hits([hit], "")
        assert app.hits and app.query_one("#results").row_count == 1
        started, release = Event(), Event()
        def pending(*args, **kwargs):
            started.set()
            assert release.wait(5)
            return [hit]
        monkeypatch.setattr(t.srch, "search", pending)
        worker = app._search("pending")
        assert await asyncio.to_thread(started.wait, 5)
        try:
            app._search("")
            assert app.hits == [] and app.query_one("#results").row_count == 0
            assert app.query_one("#detail").lines == []
            assert "searching" not in str(app.query_one("#status").render())
        finally:
            release.set()
        await worker.wait()
        assert app.hits == [] and app.query_one("#results").row_count == 0


@pytest.mark.asyncio
async def test_facet_selection_passes_exact_kind_and_source(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from mdbx import index
    from mdbx import tui as t
    db = tmp_path / "synthetic.sqlite"
    con = index.connect(db); con.close()
    seen = []
    monkeypatch.setattr(t.srch, "search", lambda *args, **kwargs: (seen.append(kwargs), [])[1])
    app = t.MdbxApp(db)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#q").value = "synthetic"
        app._facet(SimpleNamespace(option=SimpleNamespace(id="recipe|selected")))
        await app.workers.wait_for_complete()
        assert seen and seen[-1]["kind"] == "recipe"
        assert seen[-1]["source"] == "selected" and seen[-1]["source_exact"] is True


@pytest.mark.asyncio
async def test_recipe_browser_keeps_valid_bounded_literal_entries(tmp_path, monkeypatch):
    from mdbx import tui as t
    root = tmp_path/"corpus"
    (root/"recipes").mkdir(parents=True)
    (root/"recipes/good.md").write_text("---\nname: [/bold]\n---\n" + "good body\n" * 5000)
    (root/"recipes/bad.md").write_bytes(b"---\nname: bad\n---\n" + b"valid prefix\n" * 1000 + b"\xff")
    monkeypatch.setenv("MDBX_CORPUS", str(root))
    db = tmp_path/"synthetic.sqlite"
    con = index.connect(db)
    index.build_keyword(con, root/"missing") if False else None
    con.execute("INSERT OR REPLACE INTO meta VALUES('corpus',?)", (str(root),))
    con.commit(); con.close()
    app = t.MdbxApp(db)
    async with app.run_test() as pilot:
        await pilot.pause()
        worker = app.action_recipes()
        await worker.wait()
        assert [hit.source for hit in app.hits] == ["[/bold]"]
        assert len(app.hits[0].text) < 20_200 and "Preview truncated" in app.hits[0].text
        assert "partial results" in str(app.query_one("#status").render())


@pytest.mark.asyncio
async def test_superseded_worker_exits_before_embedding_search(tmp_path, monkeypatch):
    import asyncio
    from threading import Event

    from mdbx import tui as t
    db = tmp_path/"synthetic.sqlite"
    con = index.connect(db); con.close()
    entered, release = Event(), Event()
    constructed, searched = [], []
    def store(con):
        constructed.append(True)
        if len(constructed) == 1:
            entered.set()
            assert release.wait(5)
        return object()
    monkeypatch.setattr(t.srch, "VectorStore", store)
    monkeypatch.setattr(t.srch, "search", lambda con, query, *a, **kw: (searched.append(query), [])[1])
    app = t.MdbxApp(db)
    async with app.run_test() as pilot:
        await pilot.pause()
        app._search("superseded")
        assert await asyncio.to_thread(entered.wait, 5)
        newest = app._search("newest")
        release.set()
        await newest.wait()
        assert searched == ["newest"]
