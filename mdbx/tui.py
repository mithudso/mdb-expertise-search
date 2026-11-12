"""tui — Textual browser for the MongoDB expertise corpus.

Layout: a search box with mode/kind cycling over a results table, a detail pane for the
selected chunk, and a facet sidebar of MongoDB areas (skills and llms sets) that scopes
the search. Modeled on the llms-explorer concept-tree browser, specialised for MongoDB.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import ClassVar

try:
    from rich.cells import cell_len, set_cell_size
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
    if width is not None and cell_len(source) + cell_len(count) > width:
        source = set_cell_size(source, max(0, width - cell_len(count) - 1)) + "…"
    label = Text.assemble(source, (count, "dim"), no_wrap=True, overflow="ellipsis")
    if width is not None:
        label.truncate(max(0, width), overflow="ellipsis")
    return label


def side_width(longest_label: int, terminal_width: int) -> int:
    """Columns for the facet sidebar: the longest label plus chrome, capped at SIDE_MAX_SHARE."""
    cap = max(1, int(terminal_width * SIDE_MAX_SHARE))
    return min(cap, max(SIDE_MIN, longest_label + SIDE_CHROME))


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
    #side { width: 30; min-width: 0; border-right: solid $primary-darken-2; }
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
        self._search_local = threading.local()
        self._search_gate = threading.Lock()
        self._longest_facet = 0
        self._facet_rows: list[tuple[str, int, str]] = []  # (source, count, option id)
        self._facet_width: int | None = None
        self._generation = 0

    def on_unmount(self) -> None:
        self._generation += 1
        self.con.close()

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
        all_sources = Text("◉ all sources", no_wrap=True)
        if width is not None:
            all_sources.truncate(max(0, width), overflow="ellipsis")
        facets.add_option(Option(all_sources, id="__all__"))
        facets.add_options(Option(facet_label(s, n, width), id=oid) for s, n, oid in self._facet_rows)
        self._facet_width = width
        if keep is not None:
            facets.highlighted = keep

    def _fit_side(self) -> None:
        width = side_width(self._longest_facet, self.size.width)
        self.query_one("#side").styles.width = width
        usable = max(0, width - SIDE_CHROME)
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
            Text(f"mode={MODES[self.mode]} · kind={kind} · scope={scope} · {extra}")
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
        self._generation += 1
        self.source = None
        q = self.query_one("#q", Input).value
        if q.strip():
            self._search(q)
            return
        row = self.con.execute("SELECT value FROM meta WHERE key='corpus'").fetchone()
        root = Path(row[0]) if row else idx.default_corpus()
        return self._recipe_worker(root, self._generation)

    @work(thread=True, exclusive=True, group="recipes")
    def _recipe_worker(self, root: Path, generation: int) -> None:
        hits = []
        unavailable = False
        try:
            items = recipemod.load(root)
        except (OSError, ValueError, UnicodeError):
            items = []
            unavailable = True
        for recipe in items:
            if generation != self._generation:
                return
            try:
                # Recipe browsing uses a bounded preview; mdbx recipe exposes the full runbook.
                with recipemod.open_confined(root, recipe.path) as stream:
                    preview = stream.read(20_001)
                if len(preview) > 20_000:
                    preview = preview[:20_000] + "\n[Preview truncated; use mdbx recipe for the complete runbook.]"
                hits.append(srch.Hit(-1, recipe.path, recipe.name, "recipe", recipe.title, 1,
                                     preview, 0.0, "recipe", recipe.summary))
            except (OSError, ValueError, UnicodeError):
                unavailable = True
        note = " · recipes (type to search within them)"
        if unavailable:
            note += " · some recipe files are unavailable; partial results"
        self.call_from_thread(self._publish_hits, generation, hits, note)

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
        self.source = None
        if oid != "__all__" and oid is not None:
            facet_kind, self.source = oid.split("|", 1)
            self.kind = KINDS.index(facet_kind)
        self._rerun()

    @on(DataTable.RowHighlighted, "#results")
    def _highlight(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self.hits):
            self._show(self.hits[event.cursor_row])

    # ---- search (worker thread so the UI never blocks on Ollama)
    def _search(self, query: str):
        self._generation += 1
        if not query.strip():
            self._render_hits([], " · enter a search query")
            return None
        return self._search_worker(query, self._generation, MODES[self.mode], KINDS[self.kind], self.source)

    def _thread_search_state(self):
        path = Path(self.db or idx.default_db()).absolute()
        def identity():
            try:
                info = path.stat()
                return str(path), info.st_dev, info.st_ino
            except FileNotFoundError:
                return str(path), None, None
        state = getattr(self._search_local, "value", None)
        if state is None or state["identity"] != identity():
            if state is not None:
                state["con"].close()
            con = idx.connect(self.db)
            state = {"identity": identity(), "con": con, "store": None}
            self._search_local.value = state
        return state

    @work(thread=True, exclusive=True)
    def _search_worker(self, query: str, generation: int, mode: str, kind: str | None, source: str | None) -> None:
        if not query.strip() or generation != self._generation:
            return
        self.call_from_thread(self._search_status, generation)
        note = ""
        hits: list[srch.Hit] = []
        # Only one embedding request runs. Waiting superseded workers exit before loading/querying.
        with self._search_gate:
            if generation != self._generation:
                return
            try:
                state = self._thread_search_state()
                con = state["con"]
                try:
                    if mode != "keyword" and state["store"] is None:
                        state["store"] = srch.VectorStore(con)
                    if generation != self._generation:
                        return
                    notes: list[str] = []
                    hits = srch.search(
                        con, query, mode, 40, kind=kind, source=source, source_exact=source is not None, notes=notes,
                        **({"store": state["store"]} if mode != "keyword" else {}),
                    )
                    if notes:
                        note = f" ⚠ {srch.fallback_note(embedmod.EmbedError('semantic backend unavailable'))}"
                except embedmod.EmbedError:
                    if generation != self._generation:
                        return
                    log.warning("semantic search unavailable, using keyword")
                    hits = srch.keyword(con, query, 40, kind=kind, source=source, source_exact=source is not None)
                    note = " (semantic search unavailable; showing keyword results only)"
            except sqlite3.Error:
                log.error("search failed")
                note = " (search failed; retry)"
        self.call_from_thread(self._publish_hits, generation, hits, note)

    def _publish_hits(self, generation: int, hits: list[srch.Hit], note: str) -> None:
        if generation == self._generation:
            self._render_hits(hits, note)

    def _search_status(self, generation: int) -> None:
        if generation == self._generation:
            self._status("searching…")

    def _render_hits(self, hits: list[srch.Hit], note: str) -> None:
        self.hits = hits
        table = self.query_one("#results", DataTable)
        table.clear()
        for h in hits:
            table.add_row(f"{h.score:.3f}", Text(h.kind), Text(h.source), Text(h.heading.split(" > ")[-1][:60]))
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
    app = MdbxApp(db)
    try:
        app.run()
    finally:
        app.con.close()
