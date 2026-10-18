"""Drive `mql-lsp` over real stdio JSON-RPC."""
import json
import subprocess
import sys

import pytest

pytest.importorskip("pygls")


def frame(obj: dict) -> bytes:
    body = json.dumps(obj).encode()
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def read_msg(proc) -> dict:
    headers = b""
    while not headers.endswith(b"\r\n\r\n"):
        headers += proc.stdout.read(1)
    n = int(next(h for h in headers.split(b"\r\n") if h.lower().startswith(b"content-length")).split(b":")[1])
    return json.loads(proc.stdout.read(n))


def request(proc, rid, method, params):
    proc.stdin.write(frame({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
    proc.stdin.flush()
    while True:
        m = read_msg(proc)
        if m.get("id") == rid:
            return m


def test_lsp_session(tmp_path):
    proc = subprocess.Popen([sys.executable, "-m", "mdbx.mql.server"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env={"MDBX_DB": str(tmp_path / "none.sqlite"), "PATH": ""})
    try:
        init = request(proc, 1, "initialize", {"processId": None, "rootUri": None, "capabilities": {}})
        caps = init["result"]["capabilities"]
        assert caps["hoverProvider"] and caps["completionProvider"] and caps["documentSymbolProvider"]
        proc.stdin.write(frame({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
        uri = "file:///t.mql"
        text = 'db.c.aggregate([\n  { $mtch: { a: 1 } },\n  { $group: { n: { $sum: 1 } } }\n])\n'
        proc.stdin.write(frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": uri, "languageId": "mql", "version": 1, "text": text}}}))
        proc.stdin.flush()
        diag = None
        while diag is None:
            m = read_msg(proc)
            if m.get("method") == "textDocument/publishDiagnostics":
                diag = m["params"]["diagnostics"]
        codes = {d["code"] for d in diag}
        assert {"unknown-operator", "missing-field"} <= codes
        typo = next(d for d in diag if d["code"] == "unknown-operator")
        assert typo["range"]["start"] == {"line": 1, "character": 4} and typo["data"]["fix"] == "$match"

        actions = request(proc, 2, "textDocument/codeAction", {
            "textDocument": {"uri": uri}, "range": typo["range"], "context": {"diagnostics": [typo]}})
        assert actions["result"][0]["edit"]["changes"][uri][0]["newText"] == "$match"

        hov = request(proc, 3, "textDocument/hover", {"textDocument": {"uri": uri}, "position": {"line": 2, "character": 5}})
        assert "$group" in hov["result"]["contents"]["value"]

        comp = request(proc, 4, "textDocument/completion", {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 7}})
        labels = {i["label"] for i in comp["result"]["items"]}
        assert "$match" in labels

        syms = request(proc, 5, "textDocument/documentSymbol", {"textDocument": {"uri": uri}})
        assert syms["result"][0]["name"] == "db.c.aggregate"
        assert [c["name"] for c in syms["result"][0]["children"]] == ["$mtch", "$group"]
    finally:
        proc.kill()
