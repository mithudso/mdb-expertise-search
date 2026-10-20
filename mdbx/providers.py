"""providers — AI provider credentials for mdbx, via the ``ai-auth`` library.

``mdbx auth …`` stores keys (macOS Keychain, service ``ai-auth/mdbx``) or signs in with OAuth for
Claude, Codex (OpenAI), Antigravity (Gemini) and Glean; ``mdbx ask`` answers a question from corpus
passages with the first available provider and falls back to on-device Apple Intelligence; ``mdbx glean``
searches Glean through an API token, an OAuth session or the Glean CLI helper (``scripts/glean_cli_helper.py``).

The library is an optional extra (``pip install 'mdb-expertise-search[ai]'`` or
``pip install -e ~/dev/libraries/ai-auth``); everything here degrades to a clear install hint without it.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

log = logging.getLogger("mdbx.providers")

APP = "mdbx"
INSTALL_HINT = ("AI providers need the ai-auth library: pip install 'mdb-expertise-search[ai]' "
                "(or pip install -e ~/dev/libraries/ai-auth)")
MAX_CONTEXT_CHARS = 12_000
SYSTEM_PROMPT = (
    "You are a MongoDB / Atlas expert answering a support engineer. Answer from the numbered corpus "
    "passages when they apply; cite them as [n]. If the passages do not cover the question, say so and "
    "answer from general MongoDB knowledge, clearly marked. Prefer concrete commands, index shapes and "
    "explain() checks over generalities. Never invent option names or version numbers."
)


class ProvidersUnavailable(RuntimeError):
    """ai-auth is not installed."""


def _lib():
    try:
        import ai_auth
    except ImportError as exc:
        raise ProvidersUnavailable(INSTALL_HINT) from exc
    return ai_auth


def available() -> bool:
    try:
        _lib()
    except ProvidersUnavailable:
        return False
    return True


def get_auth():
    """The ``ai_auth.Auth`` facade scoped to the ``mdbx`` app namespace."""
    return _lib().Auth(APP)


def auth_cli(argv: Sequence[str]) -> int:
    """Run the ``ai-auth`` CLI as ``mdbx auth …`` (same subcommands, app pinned to mdbx)."""
    _lib()
    from ai_auth import cli as aicli

    return aicli.main(["--app", APP, *argv])


def build_context(hits, limit_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, list[dict]]:
    """Number the search hits into a prompt context block; returns (text, sources)."""
    parts: list[str] = []
    sources: list[dict] = []
    used = 0
    for i, h in enumerate(hits, 1):
        body = " ".join(h.text.split())
        room = limit_chars - used
        if room <= 200:
            break
        body = body[: min(len(body), room)]
        parts.append(f"[{i}] {h.source} · {h.heading} ({h.location})\n{body}")
        sources.append({"n": i, "source": h.source, "heading": h.heading, "location": h.location,
                        "kind": h.kind})
        used += len(body) + 80
    return "\n\n".join(parts), sources


def ask(question: str, hits, *, provider: str = "auto", model: str | None = None,
        timeout: float = 180.0, allow_apple: bool = True):
    """Answer ``question`` from ``hits``; returns (ChatResult, sources). Raises ai_auth errors."""
    auth = get_auth()
    context, sources = build_context(hits)
    prompt = (f"Question: {question}\n\nCorpus passages:\n{context or '(no matching passages)'}\n\n"
              "Answer:")
    log.debug("ask provider=%s model=%s hits=%d context_chars=%d", provider, model, len(sources), len(context))
    result = auth.chat(prompt, provider=provider, system=SYSTEM_PROMPT, model=model, timeout=timeout,
                       allow_apple=allow_apple)
    return result, sources


def glean_search(query: str, *, page_size: int = 10, datasources: list[str] | None = None) -> dict:
    return get_auth().glean.search(query, page_size=page_size, datasources=datasources)
