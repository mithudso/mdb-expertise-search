"""server — `mql-lsp`, a Language Server Protocol server for MQL.

Features: diagnostics (syntax + semantic lint), completion (operators by context, system
variables, collection methods), hover (operator docs plus optional mdbx corpus hits), document
symbols (statements and pipeline stages) and quick fixes for misspelled operators.
Run over stdio:  ``mql-lsp``.
"""
from __future__ import annotations

import logging
import sys

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .. import __version__
from . import features
from .analyze import Diag, Result, analyze

log = logging.getLogger("mql-lsp")

_SEV = {
    "error": types.DiagnosticSeverity.Error,
    "warning": types.DiagnosticSeverity.Warning,
    "info": types.DiagnosticSeverity.Information,
    "hint": types.DiagnosticSeverity.Hint,
}
_SYM_KIND = {
    "variable": types.SymbolKind.Variable,
    "method": types.SymbolKind.Method,
    "stage": types.SymbolKind.Struct,
}
_COMPLETION_KIND = {
    "operator": types.CompletionItemKind.Function,
    "stage": types.CompletionItemKind.Class,
    "variable": types.CompletionItemKind.Variable,
    "method": types.CompletionItemKind.Method,
    "key": types.CompletionItemKind.Property,
    "snippet": types.CompletionItemKind.Snippet,
}


def _u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def offset_to_position(text: str, offset: int) -> types.Position:
    offset = max(0, min(offset, len(text)))
    line = text.count("\n", 0, offset)
    line_start = text.rfind("\n", 0, offset) + 1
    return types.Position(line=line, character=_u16(text[line_start:offset]))


def position_to_offset(text: str, pos: types.Position) -> int:
    lines = text.split("\n")
    if pos.line >= len(lines):
        return len(text)
    base = sum(len(l) + 1 for l in lines[: pos.line])
    units = 0
    for i, ch in enumerate(lines[pos.line]):
        if units >= pos.character:
            return base + i
        units += _u16(ch)
    return base + len(lines[pos.line])


def to_diagnostic(text: str, d: Diag) -> types.Diagnostic:
    return types.Diagnostic(
        range=types.Range(offset_to_position(text, d.start), offset_to_position(text, d.end)),
        message=d.message,
        severity=_SEV[d.severity],
        code=d.code,
        source="mql",
        data={"fix": d.fix} if d.fix else None,
    )


def make_expertise_lookup():
    """Return a callable ``term -> ["path:line — heading", ...]`` backed by the mdbx index, or None."""
    try:
        from .. import index as idx
        from .. import search as srch

        db = idx.default_db()
        if not db.exists():
            return None

        def lookup(term: str) -> list[str]:
            con = idx.connect(db)
            try:
                hits = srch.keyword(con, term.lstrip("$") + " mongodb", 2, kind="skill")
                return [f"`{h.location}` — {h.heading.split(' > ')[-1]}" for h in hits]
            finally:
                con.close()

        return lookup
    except Exception:
        log.debug("expertise lookup unavailable", exc_info=True)
        return None


def build_server() -> LanguageServer:
    server = LanguageServer("mql-lsp", __version__, text_document_sync_kind=types.TextDocumentSyncKind.Full)
    results: dict[str, Result] = {}
    expertise = make_expertise_lookup()

    def refresh(uri: str) -> Result:
        doc = server.workspace.get_text_document(uri)
        res = analyze(doc.source)
        results[uri] = res
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=[to_diagnostic(res.text, d) for d in res.diagnostics])
        )
        return res

    def current(uri: str) -> Result:
        return results.get(uri) or refresh(uri)

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: types.DidOpenTextDocumentParams) -> None:
        refresh(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: types.DidChangeTextDocumentParams) -> None:
        refresh(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(params: types.DidCloseTextDocumentParams) -> None:
        results.pop(params.text_document.uri, None)
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
        )

    @server.feature(types.TEXT_DOCUMENT_COMPLETION, types.CompletionOptions(trigger_characters=["$", ".", ":"]))
    def completion(params: types.CompletionParams) -> types.CompletionList:
        res = current(params.text_document.uri)
        off = position_to_offset(res.text, params.position)
        items = []
        for c in features.completions(res, off):
            items.append(types.CompletionItem(
                label=c.label,
                kind=_COMPLETION_KIND[c.kind],
                detail=c.detail,
                documentation=types.MarkupContent(types.MarkupKind.Markdown, c.doc) if c.doc else None,
                insert_text_format=types.InsertTextFormat.Snippet,
                text_edit=types.TextEdit(
                    types.Range(offset_to_position(res.text, c.start), params.position), c.insert
                ),
                filter_text=c.label,
                sort_text=("0" if c.kind in {"stage", "key"} else "1") + c.label,
            ))
        return types.CompletionList(is_incomplete=False, items=items)

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    def hover(params: types.HoverParams) -> types.Hover | None:
        res = current(params.text_document.uri)
        off = position_to_offset(res.text, params.position)
        w = features.word_at(res.text, off)
        if not w:
            return None
        md = features.hover_markdown(w[0], expertise)
        if not md:
            return None
        return types.Hover(
            contents=types.MarkupContent(types.MarkupKind.Markdown, md),
            range=types.Range(offset_to_position(res.text, w[1]), offset_to_position(res.text, w[2])),
        )

    @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def symbols(params: types.DocumentSymbolParams) -> list[types.DocumentSymbol]:
        res = current(params.text_document.uri)

        def conv(s) -> types.DocumentSymbol:
            rng = types.Range(offset_to_position(res.text, s.start), offset_to_position(res.text, s.end))
            return types.DocumentSymbol(
                name=s.name, kind=_SYM_KIND[s.kind], range=rng, selection_range=rng,
                children=[conv(c) for c in s.children] or None,
            )

        return [conv(s) for s in res.symbols]

    @server.feature(
        types.TEXT_DOCUMENT_CODE_ACTION,
        types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
    )
    def code_action(params: types.CodeActionParams) -> list[types.CodeAction]:
        actions = []
        for d in params.context.diagnostics:
            fix = (d.data or {}).get("fix") if isinstance(d.data, dict) else None
            if not fix:
                continue
            actions.append(types.CodeAction(
                title=f"Replace with {fix}",
                kind=types.CodeActionKind.QuickFix,
                diagnostics=[d],
                is_preferred=True,
                edit=types.WorkspaceEdit(changes={params.text_document.uri: [types.TextEdit(d.range, fix)]}),
            ))
        return actions

    return server


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    build_server().start_io()


if __name__ == "__main__":
    main()
