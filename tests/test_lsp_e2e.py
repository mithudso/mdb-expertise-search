"""Drive `mql-lsp` over real stdio JSON-RPC."""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

import pytest

pytest.importorskip("pygls")


def frame(obj: dict) -> bytes:
    body = json.dumps(obj).encode()
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def _read_frame(stream) -> dict:
    headers = bytearray()
    while not headers.endswith(b"\r\n\r\n"):
        char = stream.read(1)
        if not char:
            raise EOFError("LSP header ended before a complete frame")
        headers.extend(char)
        if len(headers) > 8192:
            raise ValueError("LSP header exceeds test protocol bound")
    matches = [re.fullmatch(rb"Content-Length:[ \t]*([0-9]+)", header, re.IGNORECASE)
               for header in headers.split(b"\r\n") if header.lower().startswith(b"content-length")]
    if len(matches) != 1 or matches[0] is None:
        raise ValueError("LSP frame needs exactly one valid Content-Length header")
    length = int(matches[0].group(1))
    if not 0 <= length <= 8 * 1024 * 1024:
        raise ValueError("LSP body exceeds test protocol bound")
    body = bytearray()
    while len(body) < length:
        part = stream.read(length - len(body))
        if not part:
            raise EOFError("LSP body ended before the declared length")
        body.extend(part)
    return json.loads(body)


def read_msg(proc, deadline=None, phase="read"):
    if not hasattr(proc, "_mql_messages"):
        proc._mql_messages = queue.Queue()
        def reader():
            try:
                while True:
                    proc._mql_messages.put(_read_frame(proc.stdout))
            except Exception as error:  # noqa: BLE001 - transfer reader failures to the test thread
                proc._mql_messages.put(error)
        proc._mql_reader = threading.Thread(target=reader, daemon=True)
        proc._mql_reader.start()
    remaining = (deadline if deadline is not None else time.monotonic() + 10) - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(f"LSP {phase} timed out; child status={proc.poll()}")
    try:
        message = proc._mql_messages.get(timeout=remaining)
    except queue.Empty:
        raise TimeoutError(f"LSP {phase} timed out; child status={proc.poll()}") from None
    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError(f"LSP {phase} timed out; child status={proc.poll()}")
    if isinstance(message, Exception):
        raise RuntimeError(f"LSP {phase} failed ({type(message).__name__}); child status={proc.poll()}") from None  # noqa: TRY004 - transported protocol failure
    return message


def request(proc, rid, method, params, timeout=10):
    deadline = time.monotonic() + timeout
    proc.stdin.write(frame({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
    proc.stdin.flush()
    while True:
        message = read_msg(proc, deadline, f"request {rid}")
        if message.get("id") == rid:
            return message


def diagnostics(proc, uri, version, timeout=10):
    deadline = time.monotonic() + timeout
    while True:
        message = read_msg(proc, deadline, "diagnostics")
        params = message.get("params", {})
        if (message.get("method") == "textDocument/publishDiagnostics" and params.get("uri") == uri
                and params.get("version", version) == version):
            return params["diagnostics"]


def close_process(proc):
    try:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
    finally:
        for stream in (proc.stdin, proc.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        reader = getattr(proc, "_mql_reader", None)
        if reader is not None:
            reader.join(timeout=1)


def assert_capabilities(caps):
    assert isinstance(caps.get("completionProvider"), dict)
    for key in ("hoverProvider", "documentSymbolProvider"):
        assert caps.get(key) is True or isinstance(caps.get(key), dict)


def test_lsp_session(tmp_path):
    proc = subprocess.Popen([sys.executable, "-m", "mdbx.mql.server"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env={**os.environ, "MDBX_DB": str(tmp_path / "none.sqlite"), "MDBX_LSP_OPTIMIZE": "0"})
    try:
        init = request(proc, 1, "initialize", {"processId": None, "rootUri": None, "capabilities": {}})
        caps = init["result"]["capabilities"]
        assert_capabilities(caps)
        proc.stdin.write(frame({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
        uri = "file:///t.mql"
        text = 'db.c.aggregate([\n  { $mtch: { a: 1 } },\n  { $group: { n: { $sum: 1 } } }\n])\n'
        proc.stdin.write(frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": uri, "languageId": "mql", "version": 1, "text": text}}}))
        proc.stdin.flush()
        diag = diagnostics(proc, uri, 1)
        codes = {d["code"] for d in diag}
        assert {"unknown-operator", "missing-field"} <= codes
        typo = next(d for d in diag if d["code"] == "unknown-operator")
        assert typo["range"]["start"] == {"line": 1, "character": 4} and typo["data"]["fix"] == "$match"

        actions = request(proc, 2, "textDocument/codeAction", {
            "textDocument": {"uri": uri}, "range": typo["range"], "context": {"diagnostics": [typo]}})
        changes = actions["result"][0]["edit"]["documentChanges"]
        assert len(changes) == 1 and changes[0]["textDocument"] == {"uri": uri, "version": 1}
        edits = changes[0]["edits"]
        assert len(edits) == 1 and edits[0]["range"] == typo["range"]
        assert typo["range"] == {"start": {"line": 1, "character": 4}, "end": {"line": 1, "character": 9}}
        lines = text.splitlines(keepends=True)
        edit = edits[0]
        start, end = edit["range"]["start"], edit["range"]["end"]
        lo = sum(map(len, lines[:start["line"]])) + start["character"]
        hi = sum(map(len, lines[:end["line"]])) + end["character"]
        assert text[:lo] + edit["newText"] + text[hi:] == text.replace("$mtch", "$match")

        hov = request(proc, 3, "textDocument/hover", {"textDocument": {"uri": uri}, "position": {"line": 2, "character": 5}})
        assert "$group" in hov["result"]["contents"]["value"]

        comp = request(proc, 4, "textDocument/completion", {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 7}})
        labels = {i["label"] for i in comp["result"]["items"]}
        assert "$match" in labels
        item = next(i for i in comp["result"]["items"] if i["label"] == "$match")
        assert item["insertTextFormat"] == 1 and item["textEdit"]["newText"] == "$match"

        syms = request(proc, 5, "textDocument/documentSymbol", {"textDocument": {"uri": uri}})
        assert syms["result"][0]["name"] == "db.c.aggregate"
        assert [c["name"] for c in syms["result"][0]["children"]] == ["$mtch", "$group"]
    finally:
        if sys.exc_info()[0] is None:
            close_process(proc)
        else:
            try:
                close_process(proc)
            except Exception:  # noqa: BLE001 - retain the original test failure
                print("LSP cleanup failed after the test failure", file=sys.stderr)


def test_protocol_eof_and_truncated_frames():
    import io
    for payload in (b"", b"Content-Length: 2\r\n", b"Content-Length: 2\r\n\r\n{"):
        with pytest.raises(EOFError):
            _read_frame(io.BytesIO(payload))


def test_protocol_deadline_and_cleanup():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        with pytest.raises(TimeoutError, match="request 7"):
            request(proc, 7, "synthetic", {}, timeout=0.05)
    finally:
        close_process(proc)
    assert proc.poll() is not None
    assert proc.stdin.closed and proc.stdout.closed
    assert not proc._mql_reader.is_alive()


def test_protocol_filters_notifications_and_accepts_option_capabilities(monkeypatch):
    assert_capabilities({"completionProvider": {}, "hoverProvider": {}, "documentSymbolProvider": {}})
    messages = iter([
        {"method": "textDocument/publishDiagnostics", "params": {"uri": "other", "diagnostics": ["wrong"]}},
        {"method": "textDocument/publishDiagnostics", "params": {"uri": "wanted", "version": 0, "diagnostics": ["old"]}},
        {"method": "textDocument/publishDiagnostics", "params": {"uri": "wanted", "version": 1, "diagnostics": ["current"]}},
    ])
    monkeypatch.setitem(globals(), "read_msg", lambda *args: next(messages))
    assert diagnostics(None, "wanted", 1) == ["current"]

@pytest.mark.parametrize("header", [
    b"Content-Length-Junk: 2", b"Content-Length: 2:9",
    b"Content-Length: 2\r\nContent-Length: 2",
])
def test_protocol_rejects_malformed_length_headers(header):
    import io
    with pytest.raises(ValueError, match="valid Content-Length"):
        _read_frame(io.BytesIO(header + b"\r\n\r\n{}"))


def test_protocol_expired_deadline_rejects_queued_response():
    from types import SimpleNamespace
    process = SimpleNamespace(_mql_messages=queue.Queue(), poll=lambda: 0)
    process._mql_messages.put({"id": 7})
    with pytest.raises(TimeoutError):
        read_msg(process, time.monotonic() - 1)


def test_protocol_cleanup_closes_remaining_stream_and_joins_after_broken_pipe():
    from types import SimpleNamespace
    calls = []
    class Broken:
        def close(self):
            calls.append("stdin")
            raise BrokenPipeError("synthetic")
    process = SimpleNamespace(
        poll=lambda: 0, wait=lambda **kw: calls.append("wait"),
        stdin=Broken(), stdout=SimpleNamespace(close=lambda: calls.append("stdout")),
        _mql_reader=SimpleNamespace(join=lambda **kw: calls.append("join")),
    )
    close_process(process)
    assert calls == ["wait", "stdin", "stdout", "join"]
