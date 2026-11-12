"""Synthetic corpus publication/read generation contracts."""
import json
import os
from pathlib import Path

import pytest

from mdbx import corpus, recipes, safety, webexport


def versions(tmp_path):
    root, staged = tmp_path / 'corpus', tmp_path / 'staged'
    for directory, generation in ((root, 'old'), (staged, 'new')):
        (directory / 'recipes').mkdir(parents=True)
        for name in ('a', 'b'):
            (directory / 'recipes' / f'{name}.md').write_text(
                f'---\nname: {generation}-{name}\ntitle: {generation} {name}\n'
                f'summary: {generation} metadata {name}\napplies_to: [synthetic]\n---\n'
                f'# {generation} heading {name}\n{generation} body {name}\n'
            )
    return root, staged


def exchange_after_first_body(monkeypatch, root, staged, trigger=1):
    chunk_text = corpus.chunk_text
    called = []

    def after_read(text, *args, **kwargs):
        called.append(True)
        if len(called) == trigger:
            parent = safety._directory(root.parent)
            try:
                safety._exchange(parent, root.name, staged.name)
            finally:
                os.close(parent)
        return chunk_text(text, *args, **kwargs)

    monkeypatch.setattr(corpus, 'chunk_text', after_read)
    return called


def test_iter_chunks_holds_one_generation_during_exchange(tmp_path, monkeypatch):
    root, staged = versions(tmp_path)
    swapped = exchange_after_first_body(monkeypatch, root, staged)
    chunks = list(corpus.iter_chunks(root))
    assert swapped
    assert [chunk.path for chunk in chunks] == ['recipes/a.md', 'recipes/b.md']
    assert all('old body' in chunk.text and 'new body' not in chunk.text for chunk in chunks)
    assert [chunk.heading for chunk in chunks] == ['old heading a', 'old heading b']


def test_export_holds_bodies_and_recipe_metadata_in_one_generation(tmp_path, monkeypatch):
    root, staged = versions(tmp_path)
    swapped = exchange_after_first_body(monkeypatch, root, staged)
    out = tmp_path / 'web'
    webexport.export(root, out, vectors=False, allow_untracked=True)
    assert swapped
    chunks = json.loads((out / 'chunks.json').read_text())
    assert all('old body' in text and 'new body' not in text for text in (row[5] for row in chunks['rows']))
    meta = json.loads((out / 'meta.json').read_text())
    assert [recipe['name'] for recipe in meta['recipes']] == ['old-a', 'old-b']
    assert [recipe['summary'] for recipe in meta['recipes']] == ['old metadata a', 'old metadata b']


def test_recipe_metadata_keeps_loader_limits_and_defaults(tmp_path):
    root = tmp_path / 'corpus'
    directory = root / 'recipes'
    directory.mkdir(parents=True)
    texts = {
        'a.md': '# plain synthetic body\n',
        'b.md': '---\nname: chosen\ntitle: Chosen title\nsummary: summary\napplies_to: [one, two]\n---\nbody\n',
        'c.md': '---\nname: missing-end\n',
        'd.md': '---\nsummary: ' + 's' * 65536 + '\n---\nbody\n',
        'e.md': '---\n' + 'key: value\n' * 1025 + '---\nbody\n',
        'readme.md': '# excluded recipe metadata\n',
    }
    for name, text in texts.items():
        (directory / name).write_text(text)
    expected = [{'name': item.name, 'title': item.title, 'summary': item.summary,
                 'applies_to': item.applies_to, 'path': item.path} for item in recipes.load(root)]
    out = tmp_path / 'web'
    webexport.export(root, out, vectors=False, allow_untracked=True)
    assert json.loads((out / 'meta.json').read_text())['recipes'] == expected


def test_read_generation_rejects_replaced_file_symlink(tmp_path, monkeypatch):
    root, _ = versions(tmp_path)
    outside = tmp_path / 'outside.md'
    outside.write_text('outside synthetic text')
    chunk_text = corpus.chunk_text
    called = []

    def after_read(text, *args, **kwargs):
        if not called:
            second = root / 'recipes' / 'b.md'
            second.unlink()
            second.symlink_to(outside)
            called.append(True)
        return chunk_text(text, *args, **kwargs)

    monkeypatch.setattr(corpus, 'chunk_text', after_read)
    with pytest.raises(ValueError, match='unreadable or unsafe'):
        list(corpus.iter_chunks(root))


def test_export_does_not_reopen_metadata_after_body_collection(tmp_path, monkeypatch):
    root, staged = versions(tmp_path)
    exchange_after_first_body(monkeypatch, root, staged, trigger=2)
    out = tmp_path / 'web'
    webexport.export(root, out, vectors=False, allow_untracked=True)
    chunks = json.loads((out / 'chunks.json').read_text())
    assert all('old body' in row[5] for row in chunks['rows'])
    meta = json.loads((out / 'meta.json').read_text())
    assert [recipe['name'] for recipe in meta['recipes']] == ['old-a', 'old-b']


def test_deep_generation_traversal_has_bounded_descriptors(tmp_path):
    resource = pytest.importorskip('resource')
    root = tmp_path / 'corpus'
    deep = root.joinpath(*(['d'] * 80))
    deep.mkdir(parents=True)
    (deep / 'synthetic.md').write_text('# Synthetic heading\nsynthetic body\n')
    previous = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(previous[0], 64), previous[1]))
        chunks = list(corpus.iter_chunks(root))
        assert len(chunks) == 1 and chunks[0].text == '# Synthetic heading\nsynthetic body'
        assert list(corpus.iter_files(root)) == [deep / 'synthetic.md']
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, previous)


def test_generation_traversal_failure_is_not_silently_skipped(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'
    child = root / 'nested'
    child.mkdir(parents=True)
    (child / 'synthetic.md').write_text('synthetic text')
    target = child.stat()
    scandir = os.scandir

    def denied(path):
        info = os.fstat(path) if isinstance(path, int) else Path(path).stat()
        if (info.st_dev, info.st_ino) == (target.st_dev, target.st_ino):
            raise PermissionError('synthetic traversal failure')
        return scandir(path)

    monkeypatch.setattr(os, 'scandir', denied)
    with pytest.raises(PermissionError, match='synthetic traversal failure'):
        list(corpus.iter_files(root))
