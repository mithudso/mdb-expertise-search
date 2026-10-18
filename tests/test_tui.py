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
