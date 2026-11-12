"""Differential Unicode61 tokenization and query ranking against in-memory SQLite."""
import json
import shutil
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import pytest

from mdbx import index, search, unicode61, webexport

ROOT = Path(__file__).resolve().parents[1]
CASES = ['Café',
 'caféine',
 'caféine',
 'é',
 'é',
 'áb',
 'Ä́',
 'Ἀθήνα',
 'ΑΘΉΝΑ',
 'ά',
 'ά',
 'ΟΣ',
 'ΌΣ',
 'Σ',
 'ς',
 'σ',
 'ガ',
 'ガ',
 'カ',
 'が',
 'が',
 '가',
 '가',
 'a゙b',
 'a᪰b',
 'aְb',
 'Ё',
 'Ё',
 'İ',
 'İ',
 'K',
 'Å',
 '漢字',
 'SORT_MERGE',
 'a\ue000b']

def oracle(text, porter=False):
    tokenizer = ("porter " if porter else "") + "unicode61 remove_diacritics 2 tokenchars '_'"
    with closing(sqlite3.connect(":memory:")) as con:
        con.execute(f'CREATE VIRTUAL TABLE f USING fts5(text, tokenize="{tokenizer}")')
        con.execute("CREATE VIRTUAL TABLE v USING fts5vocab(f, 'instance')")
        con.execute("INSERT INTO f VALUES (?)", (text,))
        return [row[0] for row in con.execute("SELECT term FROM v ORDER BY offset")]

@pytest.mark.parametrize("text", CASES)
def test_unicode61_fold_and_boundaries_match_sqlite(text):
    assert unicode61.raw_tokens(text) == oracle(text)
    assert webexport.tokens(text) == oracle(text, porter=True)

@pytest.mark.parametrize("query", [*CASES, "why is cafe\u0301ine slow", "ΟΣ and ガ", "the and of"])
def test_query_lexemes_match_sqlite_and_export(query):
    words = oracle(query)
    kept = [word for word in words if word not in webexport.STOPWORDS] or words
    assert search._terms(query) == kept
    expected = [term for word in kept for term in oracle(word, porter=True)]
    assert webexport.query_terms(query) == expected

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_unicode61_tokens_queries_and_utf16_spans():
    queries = [*CASES, "why is cafe\u0301ine slow", "ΟΣ and ガ", "the and of", '\U00010400a', 'x \U00010400a z', 'a,b', 'a\u0301 b']
    script = """
import {readFileSync} from 'node:fs';
import {tokens,queryTerms,rawTokenSpans} from './editors/chrome/lib/textsearch.js';
const texts = JSON.parse(readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(texts.map(text => ({tokens:tokens(text),query:queryTerms(text),spans:rawTokenSpans(text)}))));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
                            input=json.dumps(queries), capture_output=True, encoding="utf-8", check=True, timeout=30)
    for text, item in zip(queries, json.loads(result.stdout), strict=True):
        assert item["tokens"] == webexport.tokens(text) == oracle(text, porter=True)
        assert item["query"] == webexport.query_terms(text)
        previous = 0
        expected = {'\U00010400a': [['\U00010428a', 0, 3]], 'x \U00010400a z': [['x',0,1],['\U00010428a',2,5],['z',6,7]], 'a,b': [['a',0,1],['b',2,3]], 'a\u0301 b': [['a',0,2],['b',3,4]]}
        if text in expected:
            assert item['spans'] == expected[text]
        for word, start, end in item["spans"]:
            assert type(start) is int and type(end) is int
            assert previous <= start < end <= len(text.encode('utf-16-le', 'surrogatepass')) // 2
            previous = end
            original = text.encode("utf-16-le", "surrogatepass")[2*start:2*end].decode("utf-16-le", "surrogatepass")
            assert unicode61.raw_tokens(original) == [word]

def test_unicode_query_ranking_matches_sqlite_and_web(tmp_path):
    corpus = tmp_path / "corpus"
    directory = corpus / "skills/mongodb-unicode"
    directory.mkdir(parents=True)
    for number, text in enumerate(CASES):
        (directory / f"case-{number:02}.md").write_text(f"# Item {number}\n\n{text}\n", encoding="utf-8")
    with closing(index.connect(tmp_path/"index.sqlite")) as con:
        index.build_keyword(con, corpus)
        webexport.export(corpus, tmp_path/"web", allow_untracked=True, vectors=False)
        exported = webexport.WebIndex(tmp_path/"web")
        specs = [{"q": query} for query in [*CASES, "cafe\u0301ine", "ΟΣ", "ガ", "가"]]
        for spec in specs:
            query = spec["q"]
            expected = [(hit.path, hit.line) for hit in search.keyword(con, query, 10)]
            actual = [(hit.path, hit.line) for hit in exported.keyword(query, 10)]
            assert actual == expected, query
        if shutil.which("node"):
            result = subprocess.run(["node", str(ROOT/"editors/chrome/test/search-batch.mjs"), str(tmp_path/"web")],
                                    input=json.dumps(specs), capture_output=True, encoding="utf-8",
                                    check=True, timeout=30)
            for spec, item in zip(specs, json.loads(result.stdout), strict=True):
                expected = [[hit.id, hit.score] for hit in exported.keyword(spec["q"], 10)]
                assert [row[0] for row in item["keyword"]] == [row[0] for row in expected]
                assert all(abs(actual[1]-wanted[1]) <= 1e-8*max(1,abs(wanted[1]))
                           for actual,wanted in zip(item["keyword"], expected, strict=True))
