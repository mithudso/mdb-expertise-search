"""Preserve tolerant shell/header parsing while validating structured query input."""
import pytest

from mdbx.mql.analyze import analyze
from mdbx.mql.normalize import normalize
from mdbx.mql.parser import parse


@pytest.mark.parametrize("value", ["{}", "{plain:1}", "{plain:1,$literal:[]}"])
def test_documents_rejects_known_plain_object_value(value):
    diagnostics = analyze("db.aggregate([{$documents:" + value + "}])").diagnostics
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "bad-argument"
    assert diagnostics[0].message == "$documents expects an array, got object."


@pytest.mark.parametrize("value", ["[]", "[{a:1}]", "{$literal:[]}", "{$let:{vars:{},in:[]}}"])
def test_documents_accepts_array_or_expression_shape(value):
    assert not analyze("db.aggregate([{$documents:" + value + "}])").diagnostics


@pytest.mark.parametrize("source", ["{}{}", "{a:1} {b:2}", "[{$match:{}}] [{$limit:1}]"])
def test_structured_same_line_input_needs_separator(source):
    assert any(error.message == "expected a statement separator" for error in parse(source)[1])
    assert normalize(source).kind == "mongosh"


@pytest.mark.parametrize("source", ["show collections", "2026-10-14 09:15 primary log excerpt"])
def test_unstructured_shell_and_log_text_remains_tolerant(source):
    assert not any(error.message == "expected a statement separator" for error in parse(source)[1])
