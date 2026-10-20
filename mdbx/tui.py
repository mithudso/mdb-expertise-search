"""tui — Textual browser for the MongoDB expertise corpus.

Layout: a search box with mode/kind cycling over a results table, a detail pane for the
selected chunk, and a facet sidebar of MongoDB areas (skills and llms sets) that scopes
the search. Modeled on the llms-explorer concept-tree browser, specialised for MongoDB.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import ClassVar

try:
    from rich.syntax import Syntax
    from rich.text import Text
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import DataTable, Footer, Header, Input, OptionList, RichLog, Static
    from textual.widgets.option_list import Option
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError("mdbx tui needs Textual — install with:  pip install 'mdb-expertise-search[tui]'") from exc

from . import embed as embedmod
from . import index as idx
from . import recipes as recipemod
from . import search as srch

log = logging.getLogger("mdbx.tui")

MODES = ["hybrid", "keyword", "semantic"]
KINDS = [None, "skill", "llms", "memory", "recipe"]

#: Facet sidebar sizing: fit the longest "source  (count)" label, but never take more than this share of
#: the terminal (the results table keeps the rest). Labels that still do not fit end in "…", never wrap.
SIDE_MAX_SHARE = 0.45
SIDE_MIN = 24
SIDE_CHROME = 10  # sidebar border/padding + option-list padding, border and scrollbar (measured)


def facet_label(source: str, n: int, width: int | None = None) -> Text:
    """ "source  (n)" with a dim count; if wider than ``width``, the source is cut to end in "…"."""
    count = f"  ({n})"
    if width is not None and len(source) + len(count) > width:
        source = source[: max(1, width - len(count) - 1)] + "…"
    return Text.assemble(source, (count, "dim"), no_wrap=True, overflow="ellipsis")


def side_width(longest_label: int, terminal_width: int) -> int:
    """Columns for the facet sidebar: the longest label plus chrome, capped at SIDE_MAX_SHARE."""
    cap = max(SIDE_MIN, int(terminal_width * SIDE_MAX_SHARE))
    return max(SIDE_MIN, min(longest_label + SIDE_CHROME, cap))


#: Quick-jump queries for common MongoDB topics (digit keys 1-9).
TOPICS = [
    ("1", "ESR compound index sort"),
    ("2", "explain executionStats COLLSCAN"),
    ("3", "replica set election oplog lag"),
    ("4", "shard key chunk migration jumbo"),
    ("5", "$lookup aggregation performance"),
    ("6", "Atlas Vector Search $vectorSearch"),
    ("7", "WiredTiger cache eviction"),
    ("8", "change streams resume token"),
    ("9", "error code troubleshooting connection"),
]


class MdbxApp(App):
    TITLE = "mdbx — MongoDB expertise"
    CSS = """
    #side { width: 30; min-width: 24; border-right: solid $primary-darken-2; }
    #side Static { padding: 0 1; color: $text-muted; }
    #main { width: 1fr; }
    #q { margin: 0 1; }
    #status { height: 1; padding: 0 1; color: $text-muted; }
    #results { height: 45%; }
    #detail { height: 1fr; border-top: solid $primary-darken-2; padding: 0 1; }
    """
    BINDINGS: ClassVar[list] = [
        Binding("ctrl+t", "cycle_mode", "Mode"),
        Binding("ctrl+k", "cycle_kind", "Kind"),
        Binding("ctrl+f", "focus_facets", "Facets"),
        Binding("ctrl+r", "recipes", "Recipes"),
        Binding("slash", "focus_query", "Search", show=False),
        Binding("escape", "clear_scope", "Clear scope"),
        Binding("q", "quit", "Quit", show=False),
        *[Binding(k, f"topic('{q}')", show=False) for k, q in TOPICS],
    ]

    def __init__(self, db: Path | None = None):
        super().__init__()
        self.db = db
        self.con: sqlite3.Connection = idx.connect(db)
        self.mode = 0
        self.kind = 0
        self.source: str | None = None
        self.hits: list[srch.Hit] = []
        self._store: srch.VectorStore | None = None
        self._longest_facet = 0
        self._facet_rows: list[tuple[str, int, str]] = []  # (source, count, option id)
        self._facet_width: int | None = None

    # ---- layout
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="side"):
                yield Static("MongoDB areas")
                yield OptionList(id="facets")
            with Vertical(id="main"):
                yield Input(placeholder="search MongoDB expertise…  (/ to focus, 1-9 topics)", id="q")
                yield Static("", id="status")
                yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
                yield RichLog(id="detail", wrap=True, markup=False, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns("Score", "Kind", "Source", "Section")
        self._facet_rows = [
            (r["source"], r["n"], f"{r['kind']}|{r['source']}")
            for r in self.con.execute(
                "SELECT source, kind, COUNT(*) n FROM chunks GROUP BY source, kind ORDER BY n DESC"
            )
        ]
        self._longest_facet = max([len("◉ all sources")] + [facet_label(s, n).cell_len for s, n, _ in self._facet_rows])
        self._fill_facets(None)
        self._fit_side()
        s = idx.stats(self.con)
        self._status(f"{s['chunks']} chunks · {s['vectors']} vectors · {s.get('embed_model', 'no embeddings')}")
        self.query_one("#q", Input).focus()

    def _fill_facets(self, width: int | None) -> None:
        facets = self.query_one("#facets", OptionList)
        keep = facets.highlighted
        facets.clear_options()
        facets.add_option(Option(Text("◉ all sources", no_wrap=True), id="__all__"))
        facets.add_options(Option(facet_label(s, n, width), id=oid) for s, n, oid in self._facet_rows)
        self._facet_width = width
        if keep is not None:
            facets.highlighted = keep

    def _fit_side(self) -> None:
        width = side_width(self._longest_facet, self.size.width)
        self.query_one("#side").styles.width = width
        usable = width - SIDE_CHROME
        target = usable if usable < self._longest_facet else None  # cut labels only when they cannot fit
        if target != self._facet_width:
            self._fill_facets(target)

    def on_resize(self) -> None:
        if self._longest_facet:
            self._fit_side()

    # ---- status / actions
    def _status(self, extra: str = "") -> None:
        kind = KINDS[self.kind] or "all kinds"
        scope = self.source or "all sources"
        self.query_one("#status", Static).update(
            f"mode={MODES[self.mode]} · kind={kind} · scope={scope} · {extra}"
        )

    def action_cycle_mode(self) -> None:
        self.mode = (self.mode + 1) % len(MODES)
        self._rerun()

    def action_cycle_kind(self) -> None:
        self.kind = (self.kind + 1) % len(KINDS)
        self._rerun()

    def action_recipes(self) -> None:
        """Show every recipe (empty query) or search within recipes when a query is typed."""
        self.kind = KINDS.index("recipe")
        self.source = None
        q = self.query_one("#q", Input).value
        if q.strip():
            self._search(q)
            return
        hits = [
            srch.Hit(-1, r.path, r.name, "recipe", r.title, 1, r.text, 0.0, "recipe", r.summary)
            for r in recipemod.load()
        ]
        self._render_hits(hits, " · recipes (type to search within them)")

    def action_focus_query(self) -> None:
        self.query_one("#q", Input).focus()

    def action_focus_facets(self) -> None:
        self.query_one("#facets", OptionList).focus()

    def action_clear_scope(self) -> None:
        self.source = None
        self._rerun()

    def action_topic(self, query: str) -> None:
        box = self.query_one("#q", Input)
        box.value = query
        self._rerun()

    def _rerun(self) -> None:
        self._search(self.query_one("#q", Input).value)

    # ---- events
    @on(Input.Submitted, "#q")
    def _submitted(self, event: Input.Submitted) -> None:
        self._search(event.value)

    @on(OptionList.OptionSelected, "#facets")
    def _facet(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id
        self.source = None if oid == "__all__" else oid.split("|", 1)[1]
        self._rerun()

    @on(DataTable.RowHighlighted, "#results")
    def _highlight(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self.hits):
            self._show(self.hits[event.cursor_row])

    # ---- search (worker thread so the UI never blocks on Ollama)
    @work(thread=True, exclusive=True)
    def _search(self, query: str) -> None:
        if not query.strip():
            return
        self.call_from_thread(self._status, "searching…")
        mode = MODES[self.mode]
        note = ""
        hits: list[srch.Hit] = []
        try:
            con = idx.connect(self.db)  # sqlite connections are thread-bound
            try:
                if mode != "keyword" and (self._store is None or not len(self._store)):
                    self._store = srch.VectorStore(con)
                notes: list[str] = []
                hits = srch.search(
                    con, query, mode, 40, kind=KINDS[self.kind], source=self.source, notes=notes,
                    **({"store": self._store} if mode != "keyword" else {}),
                )
                if notes:  # hybrid ran keyword-only because the embedder is down: say so in the status bar
                    note = f" ⚠ {notes[0]}"
            except embedmod.EmbedError as exc:
                log.warning("semantic search unavailable, using keyword: %s", exc)
                hits = srch.keyword(con, query, 40, kind=KINDS[self.kind], source=self.source)
                note = f" (semantic unavailable: {exc}; showing keyword)"
            finally:
                con.close()
        except sqlite3.Error as exc:  # an unhandled worker error would tear down the whole TUI
            log.exception("search failed")
            note = f" (search failed: {exc})"
        self.call_from_thread(self._render_hits, hits, note)

    def _render_hits(self, hits: list[srch.Hit], note: str) -> None:
        self.hits = hits
        table = self.query_one("#results", DataTable)
        table.clear()
        for h in hits:
            table.add_row(f"{h.score:.3f}", h.kind, h.source, Text(h.heading.split(" > ")[-1][:60]))
        self._status(f"{len(hits)} results{note}")
        if hits:
            table.move_cursor(row=0)
            self._show(hits[0])
        else:
            self.query_one("#detail", RichLog).clear()

    def _show(self, h: srch.Hit) -> None:
        log = self.query_one("#detail", RichLog)
        log.clear()
        log.write(Text(f"{h.location}\n{h.heading}\n", style="bold"))
        log.write(Syntax(h.text, "markdown", word_wrap=True, theme="ansi_dark", background_color="default"))


def run(db: Path | None = None) -> None:
    MdbxApp(db).run()
