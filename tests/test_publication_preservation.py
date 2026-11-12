"""Focused uncooperative-writer publication regressions; all data is synthetic."""

import errno
import os
import tempfile
from pathlib import Path

import pytest

from mdbx import safety


@pytest.fixture(autouse=True)
def exact_source_under_test():
    expected = Path(
        os.environ.get(
            "MDBX_PUBLICATION_SOURCE",
            str(Path(__file__).resolve().parents[1] / "mdbx/safety.py"),
        )
    )
    assert Path(safety.__file__).resolve() == expected.resolve()


def make_pair(tmp_path, names=("a", "b")):
    live, stage = tmp_path / "live", tmp_path / "stage"
    live.mkdir()
    stage.mkdir()
    for name in names:
        (live / name).write_bytes(("old " + name).encode())
        (stage / name).write_bytes(("new " + name).encode())
    return live, stage


def hook(monkeypatch, callback):
    if hasattr(safety, "_rename_exclusive"):
        real = safety._rename_exclusive
        monkeypatch.setattr(
            safety,
            "_rename_exclusive",
            lambda source, target, **kw: callback(real, source, target, **kw),
        )
    else:
        real = os.replace
        monkeypatch.setattr(
            os,
            "replace",
            lambda source, target, **kw: callback(real, source, target, **kw),
        )


def recoveries(live):
    return [
        p.read_bytes()
        for root in live.glob(".mdbx-recovery-*")
        for p in ([root] if root.is_file() else root.rglob("*"))
        if p.is_file()
    ]


def test_gap_writer_is_never_overwritten_and_both_versions_survive(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path, ("a",))
    inserted = []

    def race(real, source, target, **kw):
        result = real(source, target, **kw)
        if source == "a" and str(target).startswith(".mdbx-recovery-") and not inserted:
            inserted.append(True)
            (live / "a").write_bytes(b"concurrent a")
        return result

    hook(monkeypatch, race)
    with pytest.raises(FileExistsError):
        safety.publish_entries(live, stage, ("a",), lock_name="synthetic")
    assert inserted == [True]
    assert (live / "a").read_bytes() == b"concurrent a"
    assert b"old a" in recoveries(live) and b"new a" in recoveries(live)


def test_restore_refuses_a_writer_created_after_candidate_evacuation(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path)
    reached = []

    def race(real, source, target, **kw):
        if source == "b" and target == "b" and kw["src_dir_fd"] != kw["dst_dir_fd"]:
            reached.append("publish")
            raise OSError("synthetic publication fault")
        if str(source).startswith(".mdbx-recovery-") and target == "a":
            reached.append("restore")
            (live / "a").write_bytes(b"rollback concurrent a")
        return real(source, target, **kw)

    hook(monkeypatch, race)
    with pytest.raises(OSError, match="publication fault"):
        safety.publish_entries(live, stage, ("a", "b"), lock_name="synthetic")
    assert reached == ["publish", "restore"]
    assert (live / "a").read_bytes() == b"rollback concurrent a"
    assert (live / "b").read_bytes() == b"old b"
    assert (
        b"old a" in recoveries(live)
        and b"new a" in recoveries(live)
        and b"new b" in recoveries(live)
    )


def test_detected_concurrent_replacement_stays_live_during_rollback(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path)
    replace = os.replace

    def race(real, source, target, **kw):
        if source == "b" and target == "b" and kw["src_dir_fd"] != kw["dst_dir_fd"]:
            writer = tmp_path / "writer"
            writer.write_bytes(b"replacement a")
            replace(writer, live / "a")
            raise OSError("synthetic publication fault")
        return real(source, target, **kw)

    hook(monkeypatch, race)
    with pytest.raises(OSError, match="publication fault"):
        safety.publish_entries(live, stage, ("a", "b"), lock_name="synthetic")
    assert (live / "a").read_bytes() == b"replacement a"
    assert b"old a" in recoveries(live)
    assert (live / "b").read_bytes() == b"old b"


def test_success_keeps_displaced_inode_for_a_late_open_descriptor_write(tmp_path):
    live, stage = make_pair(tmp_path, ("a",))
    with (live / "a").open("r+b") as writer:
        safety.publish_entries(live, stage, ("a",), lock_name="synthetic")
        writer.seek(0)
        writer.write(b"late inode write")
        writer.truncate()
        writer.flush()
    assert (live / "a").read_bytes() == b"new a"
    assert b"late inode write" in recoveries(live)


def test_recovery_name_collision_never_overwrites_preexisting_data(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path, ("a",))
    collisions = []

    def collision(real, source, target, **kw):
        if (
            source == "a"
            and str(target).startswith(".mdbx-recovery-")
            and kw["src_dir_fd"] == kw["dst_dir_fd"]
        ):
            (live / target).write_bytes(b"preexisting recovery")
            collisions.append(target)
        return real(source, target, **kw)

    hook(monkeypatch, collision)
    with pytest.raises(FileExistsError):
        safety.publish_entries(live, stage, ("a",), lock_name="synthetic")
    assert (
        len(collisions) == 1
        and (live / collisions[0]).read_bytes() == b"preexisting recovery"
    )
    assert (live / "a").read_bytes() == b"old a"


def test_unavailable_rename_fails_before_any_generation_member_moves(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path)
    attempts = []

    def unavailable(_real, source, target, **kw):
        attempts.append((source, target))
        raise RuntimeError("exclusive generation rename unavailable")

    hook(monkeypatch, unavailable)
    with pytest.raises(RuntimeError, match="unavailable"):
        safety.publish_entries(live, stage, ("a", "b"), lock_name="synthetic")
    assert attempts and all(source not in ("a", "b") for source, _ in attempts)
    assert [(live / n).read_bytes() for n in ("a", "b")] == [b"old a", b"old b"]
    assert [(stage / n).read_bytes() for n in ("a", "b")] == [b"new a", b"new b"]
    assert not list(live.glob(".mdbx-recovery-*"))
    assert not list(live.glob(".mdbx-probe-*")) and not list(
        stage.glob(".mdbx-probe-*")
    )


def test_kernel_ignoring_exclusive_flag_is_detected_using_only_owned_probes(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path)
    if hasattr(safety, "_rename_exclusive"):
        monkeypatch.setattr(safety, "_rename_exclusive", os.replace)
    with pytest.raises(RuntimeError, match="collision"):
        safety.publish_entries(live, stage, ("a", "b"), lock_name="synthetic")
    assert [(live / n).read_bytes() for n in ("a", "b")] == [b"old a", b"old b"]
    assert [(stage / n).read_bytes() for n in ("a", "b")] == [b"new a", b"new b"]
    assert not list(live.glob(".mdbx-probe-*")) and not list(
        stage.glob(".mdbx-probe-*")
    )


def test_cross_device_capability_failure_precedes_live_displacement(
    tmp_path, monkeypatch
):
    live, stage = make_pair(tmp_path)
    moves = []

    def device(real, source, target, **kw):
        if kw["src_dir_fd"] != kw["dst_dir_fd"]:
            raise OSError(errno.EXDEV, "synthetic cross-device rename")
        moves.append(source)
        return real(source, target, **kw)

    hook(monkeypatch, device)
    with pytest.raises(OSError) as caught:
        safety.publish_entries(live, stage, ("a", "b"), lock_name="synthetic")
    assert caught.value.errno == errno.EXDEV
    assert not any(name in ("a", "b") for name in moves)
    assert [(live / n).read_bytes() for n in ("a", "b")] == [b"old a", b"old b"]


def test_publish_files_failure_does_not_recursively_delete_staging_replacements(
    tmp_path, monkeypatch
):
    staged = tmp_path / "private-staging"
    staged.mkdir()
    live = tmp_path / "live"
    live.mkdir()
    called = []
    monkeypatch.setattr(tempfile, "mkdtemp", lambda *a, **kw: str(staged))

    def failure(directory, source, names, **kwargs):
        called.append(True)
        (Path(source) / "concurrent").write_bytes(b"staged concurrent inode")
        raise OSError("synthetic preserve staging")

    monkeypatch.setattr(safety, "publish_entries", failure)
    with pytest.raises(OSError, match="preserve staging"):
        safety.publish_files(live, {"a": b"new a"}, lock_name="synthetic")
    assert called == [True]
    assert (staged / "concurrent").read_bytes() == b"staged concurrent inode"
    assert (staged / "a").read_bytes() == b"new a"


def test_success_handles_files_and_directories_without_hardlinks(tmp_path, monkeypatch):
    live, stage = make_pair(tmp_path, ("a",))
    (live / "folder").mkdir()
    (live / "folder/member").write_bytes(b"old directory")
    (stage / "folder").mkdir()
    (stage / "folder/member").write_bytes(b"new directory")
    monkeypatch.setattr(
        os, "link", lambda *a, **kw: pytest.fail("hard link primitive must not be used")
    )
    safety.publish_entries(live, stage, ("a", "folder"), lock_name="synthetic")
    assert (live / "a").read_bytes() == b"new a" and (
        live / "folder/member"
    ).read_bytes() == b"new directory"
    assert b"old a" in recoveries(live) and b"old directory" in recoveries(live)


def test_platform_exclusive_flags_and_descriptors_are_exact(monkeypatch):
    import ctypes

    if not hasattr(safety, "_rename_exclusive"):
        pytest.fail("no exclusive rename primitive")

    class Native:
        def __init__(self):
            self.calls = []

        def __call__(self, *args):
            self.calls.append(args)
            return 0

    for platform, symbol, flag in [
        ("darwin", "renameatx_np", 4),
        ("linux", "renameat2", 1),
    ]:
        native = Native()
        library = type("Library", (), {symbol: native})()
        monkeypatch.setattr(ctypes, "CDLL", lambda *a, _library=library, **kw: _library)
        monkeypatch.setattr(safety.sys, "platform", platform)
        safety._rename_exclusive("source", "target", src_dir_fd=123, dst_dir_fd=456)
        assert native.calls == [(123, b"source", 456, b"target", flag)]
