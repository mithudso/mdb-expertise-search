"""mdbx auth / ask / glean: the ai-auth adapter and CLI routing.

Tests that need the ai-auth library skip when it is not installed (it is an optional extra); the
"not installed" behaviour is always exercised.
"""
from __future__ import annotations

import builtins
import json
import sys
import types

import pytest

from mdbx import cli, providers
from mdbx.search import Hit


def _hit(i: int, text: str = "Equality, Sort, Range: order compound index keys that way.") -> Hit:
    return Hit(id=i, path=f"skills/s{i}/SKILL.md", source=f"skill-{i}", kind="skill", heading=f"H{i}",
               line=10 + i, text=text, score=1.0 / i, via="keyword")


def test_build_context_numbers_and_caps():
    text, sources = providers.build_context([_hit(1), _hit(2, "x " * 3000)], limit_chars=1500)
    assert text.startswith("[1] skill-1 · H1 (skills/s1/SKILL.md:11)")
    assert len(sources) == 2 and sources[1]["n"] == 2
    assert len(text) < 1900  # second passage truncated to the remaining room


def test_build_context_stops_when_full():
    hits = [_hit(i, "word " * 400) for i in range(1, 20)]
    _, sources = providers.build_context(hits, limit_chars=5000)
    assert 1 < len(sources) < 19


def test_missing_library_paths(monkeypatch, capsys):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "ai_auth" or name.startswith("ai_auth."):
            raise ImportError("no ai_auth")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "ai_auth", raising=False)
    assert providers.available() is False
    assert cli.main(["auth", "status"]) == 2
    assert cli.main(["ask", "why"]) == 2
    assert cli.main(["glean", "x"]) == 2
    err = capsys.readouterr().err
    assert "ai-auth" in err and "pip install" in err


def test_auth_passthrough_pins_app(monkeypatch):
    aicli = pytest.importorskip("ai_auth.cli")
    seen = {}
    monkeypatch.setattr(aicli, "main", lambda argv: seen.setdefault("argv", argv) and 0)
    assert cli.main(["auth", "set-key", "claude", "--stdin"]) == 0
    assert seen["argv"] == ["--app", "mdbx", "set-key", "claude", "--stdin"]
    seen.clear()
    assert cli.main(["auth"]) == 0
    assert seen["argv"] == ["--app", "mdbx", "status"]


class _FakeAuth:
    def __init__(self, text="answer [1]", provider="apple"):
        self.calls = []
        self.text, self.provider_name = text, provider
        self.glean = self

    def chat(self, prompt, **kw):
        self.calls.append((prompt, kw))
        return types.SimpleNamespace(text=self.text, provider=self.provider_name, kind="local",
                                     model="m", raw={})

    def search(self, query, page_size=10, datasources=None):
        self.calls.append(("glean", query, page_size, datasources))
        return {"ok": True, "query": query, "results": [{"title": "T", "url": "https://g/1", "snippet": "s",
                                                           "datasource": "confluence", "doc_type": "", "updated": ""}],
                "cursor": None, "raw_count": 1}


def test_ask_builds_prompt_and_prints_sources(monkeypatch, tmp_path, capsys):
    pytest.importorskip("ai_auth")
    fake = _FakeAuth()
    monkeypatch.setattr(providers, "get_auth", lambda: fake)
    monkeypatch.setattr(cli.idx, "connect", lambda db: object())
    monkeypatch.setattr(cli.idx, "stats", lambda con: {"chunks": 5})
    monkeypatch.setattr(cli.srch, "search", lambda con, q, mode, limit, **kw: [_hit(1), _hit(2)])
    assert cli.main(["ask", "-p", "apple", "-n", "2", "what", "is", "ESR"]) == 0
    out = capsys.readouterr()
    assert "answer [1]" in out.out and "[1] skill-1 · H1" in out.out and "[2] skill-2" in out.out
    prompt, kw = fake.calls[0]
    assert prompt.startswith("Question: what is ESR") and "[2] skill-2 · H2" in prompt
    assert kw["provider"] == "apple" and kw["system"] == providers.SYSTEM_PROMPT and kw["allow_apple"] is True
    assert "[apple · local · m]" in out.err


def test_ask_json_and_empty_index(monkeypatch, capsys):
    pytest.importorskip("ai_auth")
    fake = _FakeAuth()
    monkeypatch.setattr(providers, "get_auth", lambda: fake)
    monkeypatch.setattr(cli.idx, "connect", lambda db: object())
    monkeypatch.setattr(cli.idx, "stats", lambda con: {"chunks": 0})
    assert cli.main(["ask", "--json", "--no-apple", "q"]) == 0
    out = capsys.readouterr()
    data = json.loads(out.out)
    assert data["answer"] == "answer [1]" and data["sources"] == [] and data["provider"] == "apple"
    assert "(no matching passages)" in fake.calls[0][0]
    assert fake.calls[0][1]["allow_apple"] is False
    assert "index is empty" in out.err


def test_ask_not_configured_message(monkeypatch, capsys):
    ai_auth = pytest.importorskip("ai_auth")

    class Boom(_FakeAuth):
        def chat(self, prompt, **kw):
            raise ai_auth.NotConfigured("Claude: no credential found.")
    monkeypatch.setattr(providers, "get_auth", lambda: Boom())
    monkeypatch.setattr(cli.idx, "connect", lambda db: object())
    monkeypatch.setattr(cli.idx, "stats", lambda con: {"chunks": 0})
    assert cli.main(["ask", "q"]) == 1
    err = capsys.readouterr().err
    assert "no credential" in err and "mdbx auth set-key" in err


def test_glean_command(monkeypatch, capsys):
    pytest.importorskip("ai_auth")
    fake = _FakeAuth()
    monkeypatch.setattr(providers, "get_auth", lambda: fake)
    assert cli.main(["glean", "-n", "3", "-d", "confluence", "private", "link"]) == 0
    out = capsys.readouterr().out
    assert "1. T  [confluence]" in out and "https://g/1" in out
    assert fake.calls[0] == ("glean", "private link", 3, ["confluence"])
    assert cli.main(["glean", "--json", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["title"] == "T"


def test_glean_helper_script_delegates(monkeypatch, capsys):
    pytest.importorskip("ai_auth")
    import runpy

    import ai_auth.glean_helper as gh
    monkeypatch.setattr(gh, "main", lambda: 0)
    monkeypatch.setattr(sys, "argv", ["glean_cli_helper.py", "check"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path("scripts/glean_cli_helper.py", run_name="__main__")
    assert exc.value.code == 0
