"""parser — a tolerant parser for mongosh-style MQL.

Accepts relaxed JSON / JavaScript object literals plus the call shapes that appear in mongosh
scripts: ``db.coll.find({...}).sort({...})``, ``ObjectId("...")``, ``ISODate(...)``, regex
literals, ``const x = [...]``. It never raises: syntax problems become ``ParseError`` records and
the parser resynchronises, so editors get a useful tree while the user is mid-edit.

All positions are 0-based character offsets into the source text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NUMBER = re.compile(r"[-+]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|Infinity|NaN)")
_KEYWORDS = {"true": "bool", "false": "bool", "null": "null", "undefined": "undefined"}
_DECL = {"const", "let", "var"}


@dataclass
class ParseError:
    start: int
    end: int
    message: str


@dataclass
class Prop:
    key: str
    key_start: int
    key_end: int
    quoted: bool
    value: Node | None
    start: int
    end: int


@dataclass
class Node:
    kind: str  # object array string number bool null undefined regex ident call member error
    start: int
    end: int
    value: object = None  # str/number/bool value, ident name, member name, regex source
    props: list[Prop] = field(default_factory=list)  # object
    items: list[Node] = field(default_factory=list)  # array / call args
    target: Node | None = None  # call callee / member object
    name_start: int = 0  # member name offset
    closed: bool = True  # object/array/call had its closing token

    def walk(self):
        yield self
        for p in self.props:
            if p.value is not None:
                yield from p.value.walk()
        for i in self.items:
            yield from i.walk()
        if self.target is not None:
            yield from self.target.walk()


@dataclass
class Statement:
    node: Node
    start: int
    end: int
    decl: str | None = None  # variable name for ``const x = ...``


class Parser:
    def __init__(self, text: str):
        self.s = text
        self.n = len(text)
        self.i = 0
        self.errors: list[ParseError] = []

    # ---- low level
    def ws(self) -> None:
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c.isspace():
                self.i += 1
            elif s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j
            elif s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                if j < 0:
                    self.err(self.i, n, "unterminated comment")
                    self.i = n
                else:
                    self.i = j + 2
            else:
                break

    def err(self, start: int, end: int, msg: str) -> None:
        self.errors.append(ParseError(start, max(end, start + 1), msg))

    def peek(self) -> str:
        self.ws()
        return self.s[self.i] if self.i < self.n else ""

    # ---- statements
    def parse(self) -> list[Statement]:
        out: list[Statement] = []
        while True:
            self.ws()
            while self.i < self.n and self.s[self.i] == ";":
                self.i += 1
                self.ws()
            if self.i >= self.n:
                break
            start = self.i
            stmt = self.statement()
            if stmt is not None:
                out.append(stmt)
            if self.i == start:  # guarantee progress
                self.err(self.i, self.i + 1, f"unexpected {self.s[self.i]!r}")
                self.i += 1
        return out

    def statement(self) -> Statement | None:
        start = self.i
        m = _IDENT.match(self.s, self.i)
        decl = None
        if m and m.group() in _DECL:
            j = m.end()
            m2 = re.compile(r"\s+([A-Za-z_$][\w$]*)\s*=").match(self.s, j)
            if m2:
                decl = m2.group(1)
                self.i = m2.end()
        elif m and m.group() == "use":
            m2 = re.compile(r"[ \t]+[\w$-]+[ \t]*(?=\n|;|$)").match(self.s, m.end())
            if m2:  # mongosh `use dbname`
                self.i = m2.end()
                return None
        node = self.expression()
        if node is None:
            self.resync()
            return None
        # a trailing token that is not ; or newline-separated start of a new statement
        self.ws()
        return Statement(node, start, node.end, decl)

    def resync(self) -> None:
        j = self.s.find("\n", self.i)
        self.i = self.n if j < 0 else j + 1

    # ---- expressions
    def expression(self) -> Node | None:
        node = self.primary()
        if node is None:
            return None
        while True:
            self.ws()
            if self.i >= self.n:
                break
            c = self.s[self.i]
            if c == ".":
                self.i += 1
                self.ws()
                m = _IDENT.match(self.s, self.i)
                if not m:
                    self.err(self.i, self.i + 1, "expected property name after '.'")
                    break
                node = Node("member", node.start, m.end(), m.group(), target=node, name_start=m.start())
                self.i = m.end()
            elif c == "(":
                node = self.call(node)
            elif c == "[" and node.kind in {"ident", "member"}:
                # computed member access (e.g. db["my-coll"]) — treat as member of unknown name
                self.i += 1
                inner = self.expression()
                self.ws()
                if self.i < self.n and self.s[self.i] == "]":
                    self.i += 1
                else:
                    self.err(self.i, self.i + 1, "expected ']'")
                name = inner.value if inner is not None and inner.kind == "string" else "?"
                node = Node("member", node.start, self.i, name, target=node, name_start=node.end)
            else:
                break
        return node

    def call(self, callee: Node) -> Node:
        open_at = self.i
        self.i += 1
        args: list[Node] = []
        closed = False
        while True:
            self.ws()
            if self.i >= self.n:
                self.err(open_at, open_at + 1, "unclosed '('")
                break
            c = self.s[self.i]
            if c == ")":
                self.i += 1
                closed = True
                break
            if c == ",":
                self.i += 1
                continue
            before = self.i
            arg = self.expression()
            if arg is None:
                self.skip_bad_value({")"})
            else:
                args.append(arg)
            if self.i == before:
                self.i += 1
        return Node("call", callee.start, self.i, target=callee, items=args, closed=closed)

    def skip_bad_value(self, closers: set[str]) -> None:
        """Advance past an unparsable value to the next ``,`` or closer at this depth."""
        depth = 0
        start = self.i
        while self.i < self.n:
            c = self.s[self.i]
            if c in "{[(":
                depth += 1
            elif c in "}])":
                if depth == 0 and c in closers:
                    break
                depth = max(depth - 1, 0)
            elif c == "," and depth == 0:
                break
            self.i += 1
        if self.i > start:
            self.err(start, self.i, "unexpected tokens")

    def primary(self) -> Node | None:
        self.ws()
        if self.i >= self.n:
            return None
        c = self.s[self.i]
        if c == "{":
            return self.object()
        if c == "[":
            return self.array()
        if c in "\"'`":
            return self.string()
        if c == "/" and not self.s.startswith("//", self.i) and not self.s.startswith("/*", self.i):
            return self.regex()
        m = _NUMBER.match(self.s, self.i)
        if m and (m.group()[0] in "+-.0123456789" or m.group() in {"Infinity", "NaN"}):
            text = m.group()
            self.i = m.end()
            try:
                val: object = int(text, 0) if text.lower().startswith(("0x", "-0x", "+0x")) else (
                    int(text) if re.fullmatch(r"[-+]?\d+", text) else float(text)
                )
            except ValueError:
                val = text
            return Node("number", m.start(), m.end(), val)
        m = _IDENT.match(self.s, self.i)
        if m:
            word = m.group()
            self.i = m.end()
            if word in _KEYWORDS:
                kind = _KEYWORDS[word]
                return Node(kind, m.start(), m.end(), word == "true" if kind == "bool" else None)
            if word == "new":
                return self.primary()
            return Node("ident", m.start(), m.end(), word)
        return None

    def string(self) -> Node:
        q = self.s[self.i]
        start = self.i
        self.i += 1
        buf: list[str] = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\" and self.i + 1 < self.n:
                nxt = self.s[self.i + 1]
                buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
                self.i += 2
                continue
            if c == q:
                self.i += 1
                return Node("string", start, self.i, "".join(buf))
            if c == "\n" and q != "`":
                break
            buf.append(c)
            self.i += 1
        self.err(start, self.i, "unterminated string")
        return Node("string", start, self.i, "".join(buf), closed=False)

    def regex(self) -> Node:
        start = self.i
        j = self.i + 1
        in_class = False
        while j < self.n:
            c = self.s[j]
            if c == "\\":
                j += 2
                continue
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif c == "/" and not in_class:
                break
            elif c == "\n":
                j = self.n
                break
            j += 1
        if j >= self.n:
            self.err(start, min(self.n, start + 1), "unterminated regular expression")
            self.i = min(self.n, start + 1)
            return Node("error", start, self.i)
        src = self.s[start + 1 : j]
        j += 1
        m = re.compile(r"[a-z]*").match(self.s, j)
        flags = m.group() if m else ""
        self.i = j + len(flags)
        return Node("regex", start, self.i, src + "/" + flags)

    def array(self) -> Node:
        start = self.i
        self.i += 1
        items: list[Node] = []
        closed = False
        while True:
            self.ws()
            if self.i >= self.n:
                self.err(start, start + 1, "unclosed '['")
                break
            c = self.s[self.i]
            if c == "]":
                self.i += 1
                closed = True
                break
            if c == ",":
                self.i += 1
                continue
            if c in "})":
                self.err(self.i, self.i + 1, f"unexpected {c!r}; expected ']'")
                break
            before = self.i
            val = self.expression()
            if val is None:
                self.skip_bad_value({"]"})
            else:
                items.append(val)
            if self.i == before:
                self.i += 1
        return Node("array", start, self.i, items=items, closed=closed)

    def object(self) -> Node:
        start = self.i
        self.i += 1
        props: list[Prop] = []
        closed = False
        while True:
            self.ws()
            if self.i >= self.n:
                self.err(start, start + 1, "unclosed '{'")
                break
            c = self.s[self.i]
            if c == "}":
                self.i += 1
                closed = True
                break
            if c == ",":
                self.i += 1
                continue
            if c in "])":
                self.err(self.i, self.i + 1, f"unexpected {c!r}; expected '}}'")
                break
            before = self.i
            prop = self.prop()
            if prop is not None:
                props.append(prop)
            if self.i == before:
                self.i += 1
        return Node("object", start, self.i, props=props, closed=closed)

    def prop(self) -> Prop | None:
        self.ws()
        k0 = self.i
        c = self.s[self.i]
        quoted = c in "\"'"
        if quoted:
            node = self.string()
            key = str(node.value)
        else:
            m = _IDENT.match(self.s, self.i) or re.compile(r"-?\d+(?:\.\d+)?").match(self.s, self.i)
            if not m:
                self.err(self.i, self.i + 1, "expected a property name")
                self.skip_bad_value({"}"})
                return None
            key = m.group()
            self.i = m.end()
        k1 = self.i
        self.ws()
        if self.i < self.n and self.s[self.i] == ":":
            self.i += 1
        elif self.i < self.n and self.s[self.i] in ",}":
            # shorthand ``{ a }`` — valid JS, meaningless in MQL
            self.err(k0, k1, f"property {key!r} has no value")
            return Prop(key, k0, k1, quoted, None, k0, k1)
        else:
            self.err(self.i, self.i + 1, "expected ':'")
            self.skip_bad_value({"}"})
            return Prop(key, k0, k1, quoted, None, k0, self.i)
        val = self.expression()
        if val is None:
            self.err(self.i, self.i + 1, f"expected a value for {key!r}")
            self.skip_bad_value({"}"})
        return Prop(key, k0, k1, quoted, val, k0, val.end if val else self.i)


def parse(text: str) -> tuple[list[Statement], list[ParseError]]:
    p = Parser(text)
    stmts = p.parse()
    return stmts, p.errors
