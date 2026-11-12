"""Adversarial preservation and privacy checks use only owned synthetic trees."""
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    if name == "rotate_workflow_logs":
        import datetime
        class FixedDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(2026, 1, 1)
        obj.dt = SimpleNamespace(date=FixedDate)
    return obj


def test_rotation_rejects_archive_alias_and_negative_retention(tmp_path, monkeypatch):
    m = module("rotate_workflow_logs"); monkeypatch.setattr(m, "ROOT", tmp_path)
    source = tmp_path / "memory.md"; original = "## v2\nkeep\n## v1\nold\n"; source.write_text(original)
    archive = tmp_path / "docs/archive" / f"memory-{m.dt.date.today().isoformat()}.md"; archive.parent.mkdir(parents=True); archive.symlink_to(source)
    with pytest.raises((OSError, ValueError, RuntimeError)): m.rotate(source, 0, 1, False)
    assert source.read_text() == original
    archive.unlink()
    with pytest.raises(ValueError, match="nonnegative"): m.rotate(source, 0, -1, False)


def test_rotation_check_and_editor_symlink_lock(tmp_path, monkeypatch):
    m = module("rotate_workflow_logs"); monkeypatch.setattr(m, "ROOT", tmp_path)
    source = tmp_path / "memory.md"; source.write_text("## v1\nkept\n")
    assert m.rotate(source, 0, 1, True) is False
    source.write_text("## v2\nkeep\n## v1\narchive\n")
    before = source.read_bytes()
    assert m.rotate(source, 0, 1, True) is True
    assert source.read_bytes() == before and not (tmp_path / "docs").exists()
    source.with_name(".#memory.md").symlink_to(tmp_path / "missing")
    with pytest.raises((SystemExit, RuntimeError)): m.rotate(source, 0, 1, False)


def test_recipe_reads_reject_outside_symlinks_and_skip_directories(tmp_path):
    from mdbx.recipes import Recipe, load
    root = tmp_path / "corpus"; (root / "recipes").mkdir(parents=True)
    outside = tmp_path / "outside.md"; outside.write_text("synthetic private content")
    (root / "recipes/link.md").symlink_to(outside)
    with pytest.raises(ValueError): _ = Recipe("x", "x", "", path="recipes/link.md", root=root).text
    (root / "recipes/link.md").unlink(); (root / "recipes/directory.md").mkdir()
    (root / "recipes/good.md").write_text("# synthetic")
    assert [r.path for r in load(root)] == ["recipes/good.md"]


def redactor(tmp_path, monkeypatch):
    m = module("redact_corpus"); (tmp_path / "corpus").mkdir(); monkeypatch.setattr(m, "ROOT", tmp_path); monkeypatch.setattr(m, "CORPUS", tmp_path / "corpus"); monkeypatch.setattr(m, "PRIVATE_FILES", []); monkeypatch.setattr(m, "load_private", lambda: ([("SYNTH_PRIVATE", "safe")], None)); return m


def test_redaction_preserves_outside_files_invalid_utf8_and_yml(tmp_path, monkeypatch):
    m = redactor(tmp_path, monkeypatch)
    outside = tmp_path / "outside.md"; outside.write_text("SYNTH_PRIVATE")
    (m.CORPUS / "link.md").symlink_to(outside)
    invalid = m.CORPUS / "bad.md"; invalid.write_bytes(b"SYNTH_PRIVATE\xff")
    yaml = m.CORPUS / "sample.yml"; yaml.write_text("SYNTH_PRIVATE")
    assert m.main() != 0
    assert outside.read_text() == "SYNTH_PRIVATE"; assert invalid.read_bytes() == b"SYNTH_PRIVATE\xff"
    assert yaml.read_text() in {"SYNTH_PRIVATE", "safe"}


def test_redaction_exact_private_file_and_idempotent_rules(tmp_path, monkeypatch):
    m = redactor(tmp_path, monkeypatch); monkeypatch.setattr(m, "PRIVATE_FILES", ["corpus/private.md", "corpus/local/"])
    assert m.is_private("corpus/private.md") and m.is_private("corpus/local/x.md")
    assert not m.is_private("corpus/private.md.notes.md")
    monkeypatch.setattr(m, "load_private", lambda: ([("B", "C"), ("A", "B")], None))
    (m.CORPUS / "x.md").write_text("A")
    assert m.main() != 0; assert (m.CORPUS / "x.md").read_text() == "A"


def test_redaction_patch_failure_is_private_and_fails(tmp_path, monkeypatch, capsys):
    m = redactor(tmp_path, monkeypatch); patch = tmp_path / "private.patch"; patch.write_text("synthetic")
    monkeypatch.setattr(m, "load_private", lambda: ([], str(patch)))
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="SYNTH_PRIVATE", stderr="SYNTH_PRIVATE"))
    assert m.main() != 0
    captured = capsys.readouterr()
    assert "SYNTH_PRIVATE" not in captured.out + captured.err


def test_sweeper_nul_names_csv_symlinks_and_private_diagnostics(tmp_path, monkeypatch, capsys):
    m = module("sweep_customers"); (tmp_path / "corpus").mkdir(); monkeypatch.setattr(m, "ROOT", tmp_path)
    names = ["corpus/a\tname.csv", "corpus/clean.md"]
    for name in names: (tmp_path / name).write_text("SYNTH_PRIVATE" if name.endswith("csv") else "clean")
    monkeypatch.setattr(m, "load_patterns", lambda: [re.compile("SYNTH_PRIVATE")])
    def listing(argv, **kwargs):
        assert "-z" in argv
        return SimpleNamespace(stdout="" if "-o" in argv else "\0".join(names) + "\0")
    monkeypatch.setattr(m.subprocess, "run", listing)
    assert m.main([]) == 1; assert "SYNTH_PRIVATE" not in "".join(capsys.readouterr())
    outside = tmp_path / "outside.md"; outside.write_text("SYNTH_PRIVATE"); (tmp_path / names[0]).unlink(); (tmp_path / names[0]).symlink_to(outside)
    assert m.main([]) == 2; assert "SYNTH_PRIVATE" not in "".join(capsys.readouterr())


def test_package_no_data_preserves_existing_data_and_artifact_failure(tmp_path, monkeypatch):
    m = module("package_chrome_extension"); ext = tmp_path / "editors/chrome"; ext.mkdir(parents=True)
    monkeypatch.setattr(m, "ROOT", tmp_path); monkeypatch.setattr(m, "EXT", ext); monkeypatch.setattr(m, "DATA", ext / "data"); monkeypatch.setattr(m, "git_commit", lambda: "synthetic")
    for name in m.RUNTIME: (ext / name).write_text("synthetic")
    (ext / "manifest.json").write_text(json.dumps({"version": "0.3.0"})); (ext / "package.json").write_text(json.dumps({"version": "0.3.0"}))
    (ext / "lib").mkdir(); (ext / "icons").mkdir()
    (ext / "data").mkdir(); sentinel = ext / "data/private.bin"; sentinel.write_bytes(b"preserve")
    monkeypatch.setattr(sys, "argv", ["package", "--no-data"])
    assert m.main() == 0; assert sentinel.read_bytes() == b"preserve"
    import zipfile
    out = tmp_path / "dist/mongodb-expertise-chrome-0.3.0.zip"; previous = out.read_bytes()
    with zipfile.ZipFile(out) as archive: assert "data/private.bin" not in archive.namelist()
    (ext / "background.js").unlink(); (ext / "background.js").symlink_to(sentinel)
    assert m.main() != 0; assert out.read_bytes() == previous


def test_rotation_failed_publish_and_intervening_append_preserve_source(tmp_path, monkeypatch):
    m = module("rotate_workflow_logs"); monkeypatch.setattr(m, "ROOT", tmp_path)
    source = tmp_path / "memory.md"; original = b"## v2\nkeep\n## v1\narchive\n"; source.write_bytes(original)
    real = m.atomic_write
    replacement = m.replace_preserving
    def fail_source(*args, **kwargs):
        raise OSError("synthetic staging failure")
    monkeypatch.setattr(m, "replace_preserving", fail_source)
    with pytest.raises(OSError): m.rotate(source, 0, 1, False)
    assert source.read_bytes() == original
    monkeypatch.setattr(m, "replace_preserving", replacement)
    archive = next((tmp_path / "docs/archive").glob("memory-*.md"))
    archive.unlink()  # Exercise append during a fresh archive publication separately from retry identity.
    def append_during_archive(path, data, *args, **kwargs):
        result = real(path, data, *args, **kwargs)
        if path.name == f"memory-{m.dt.date.today().isoformat()}.md":
            with source.open("ab") as stream: stream.write(b"concurrent append\n")
        return result
    monkeypatch.setattr(m, "atomic_write", append_during_archive)
    with pytest.raises(RuntimeError, match="changed"): m.rotate(source, 0, 1, False)
    assert source.read_bytes() == original + b"concurrent append\n"


def test_rotation_archive_batches_keep_a_line_boundary(tmp_path, monkeypatch):
    m = module("rotate_workflow_logs"); monkeypatch.setattr(m, "ROOT", tmp_path)
    source = tmp_path / "memory.md"; source.write_text("## v2\nkeep\n## v1\narchive\n")
    archive = tmp_path / "docs/archive" / f"memory-{m.dt.date.today().isoformat()}.md"; archive.parent.mkdir(parents=True); archive.write_text("previous without newline")
    assert m.rotate(source, 0, 1, False)
    assert archive.read_text().startswith("previous without newline\n<!-- mdbx-rotation:")
    assert "\n## v1" in archive.read_text()


def test_redaction_preserves_lines_and_processes_yaml(tmp_path, monkeypatch):
    m = redactor(tmp_path, monkeypatch); path = m.CORPUS / "sample.yml"; path.write_text("before\n(HELP-123)\nSYNTH_PRIVATE\n")
    assert m.main() == 0
    assert path.read_text() == "before\n\nsafe\n"
    assert m.main() == 0


def test_invalid_private_pattern_diagnostic_is_opaque(tmp_path, monkeypatch, capsys):
    m = module("sweep_customers"); deny = tmp_path / "deny"; deny.write_text("SYNTH_SECRET[\n")
    monkeypatch.setenv("MDBX_DENYLIST", str(deny))
    with pytest.raises(SystemExit) as error: m.load_patterns()
    captured = capsys.readouterr()
    assert "SYNTH_SECRET" not in str(error.value) + captured.out + captured.err


def test_rotation_preserves_delayed_writer_on_the_original_inode(tmp_path, monkeypatch):
    m = module("rotate_workflow_logs"); monkeypatch.setattr(m, "ROOT", tmp_path)
    source = tmp_path / "memory.md"; source.write_text("## v2\nkeep\n## v1\narchive\n")
    real = m.replace_preserving
    with source.open("ab") as delayed_writer:
        def publish_then_append(path, data, *args, **kwargs):
            result = real(path, data, *args, **kwargs)
            if path == source:
                delayed_writer.write(b"late uncooperative append\n"); delayed_writer.flush()
            return result
        monkeypatch.setattr(m, "replace_preserving", publish_then_append)
        assert m.rotate(source, 0, 1, False)
    retained = [path.read_bytes() for path in tmp_path.rglob("*") if path.is_file() and path != source]
    assert any(b"late uncooperative append\n" in body for body in retained)
    assert source.read_text() == "## v2\nkeep\n"
