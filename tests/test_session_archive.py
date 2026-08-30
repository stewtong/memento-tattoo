from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from memento_tattoo.rebuild import rebuild
from memento_tattoo.session_archive import ArchiveMove, apply_archive, archive_candidates
from memento_tattoo.session_store import duplicate_session_ids, load_sessions, render_session_block


def _write_session(root: Path, sess: str, session_date: str, *, archive: bool = False) -> Path:
    directory = root / "sessions" / ("archive" if archive else "")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{sess}.md"
    path.write_text(
        render_session_block(
            sess,
            date=session_date,
            agent="codex",
            topics=["tests"],
            significance="medium",
            accomplished=f"Recorded {sess}.",
            started="none.",
            pending="none.",
            insights="none.",
            files=[],
        ),
        encoding="utf-8",
    )
    return path


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_candidates_use_parsed_date_exclude_cutoff_and_dry_run_is_pure(tmp_path: Path):
    old = _write_session(tmp_path, "sess_old", "2026-06-19 23:59")
    cutoff = _write_session(tmp_path, "sess_cutoff", "2026-06-20 00:00")
    old.touch()
    cutoff.touch()
    before = _snapshot(tmp_path)

    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))

    assert [move.session_id for move in moves] == ["sess_old"]
    assert _snapshot(tmp_path) == before


def test_candidates_limit_is_restartable_and_zero_means_all(tmp_path: Path):
    for index in range(4):
        _write_session(tmp_path, f"sess_{index}", f"2026-06-0{index + 1} 10:00")

    bounded = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30), limit=2)
    unbounded = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30), limit=0)

    assert [move.session_id for move in bounded] == ["sess_0", "sess_1"]
    assert len(unbounded) == 4


def test_invalid_session_or_date_fails_selection(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_bad.md").write_text("[sess_bad | not-a-date | codex | tests | low]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid session date"):
        archive_candidates(tmp_path, days=1, today=date(2026, 6, 30))


def test_complete_batch_validation_prevents_any_move_on_missing_source(tmp_path: Path):
    first = _write_session(tmp_path, "sess_first", "2026-06-01 10:00")
    second = _write_session(tmp_path, "sess_second", "2026-06-02 10:00")
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    second.unlink()

    with pytest.raises(FileNotFoundError):
        apply_archive(moves, tmp_path)

    assert first.exists()
    assert not (tmp_path / "sessions" / "archive" / first.name).exists()


def test_destination_conflict_prevents_whole_batch(tmp_path: Path):
    first = _write_session(tmp_path, "sess_first", "2026-06-01 10:00")
    second = _write_session(tmp_path, "sess_second", "2026-06-02 10:00")
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    conflict = tmp_path / "sessions" / "archive" / second.name
    conflict.parent.mkdir()
    conflict.write_text("occupied", encoding="utf-8")

    with pytest.raises((FileExistsError, ValueError)):
        apply_archive(moves, tmp_path)

    assert first.exists()
    assert second.exists()


def test_duplicate_id_conflict_prevents_whole_batch(tmp_path: Path):
    hot = _write_session(tmp_path, "sess_dup", "2026-06-01 10:00")
    archived = _write_session(tmp_path, "sess_dup", "2026-05-01 10:00", archive=True)
    archived.rename(archived.with_name("sess_other_filename.md"))
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))

    with pytest.raises(ValueError, match="conflicting session IDs"):
        apply_archive(moves, tmp_path)

    assert hot.exists()


def test_apply_preserves_bytes_ids_and_archive_visibility_then_repeats_as_noop(tmp_path: Path):
    source = _write_session(tmp_path, "sess_old", "2026-06-01 10:00")
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))

    assert apply_archive(moves, tmp_path) == 1
    destination = tmp_path / "sessions" / "archive" / source.name
    assert not source.exists()
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == original_hash
    assert [record.sess for record in load_sessions(tmp_path)] == ["sess_old"]
    assert duplicate_session_ids(tmp_path) == {}
    assert "sess_old" in (tmp_path / "sessions" / "index.md").read_text(encoding="utf-8")
    assert rebuild(tmp_path, check=True) == (True, "session indexes current")

    before = _snapshot(tmp_path)
    repeat = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    assert repeat == []
    assert apply_archive(repeat, tmp_path) == 0
    assert _snapshot(tmp_path) == before


def test_apply_rejects_duplicate_moves_before_mutation(tmp_path: Path):
    source = _write_session(tmp_path, "sess_old", "2026-06-01 10:00")
    destination = tmp_path / "sessions" / "archive" / source.name
    move = ArchiveMove(source, destination, "sess_old", "2026-06-01 10:00")

    with pytest.raises(ValueError, match="duplicate sources"):
        apply_archive([move, move], tmp_path)

    assert source.exists()


def test_second_rename_failure_restores_exact_current_indexes_and_created_archive(tmp_path: Path, monkeypatch):
    import memento_tattoo.session_archive as session_archive

    first = _write_session(tmp_path, "sess_first", "2026-06-01 10:00")
    second = _write_session(tmp_path, "sess_second", "2026-06-02 10:00")
    index = tmp_path / "sessions" / "index.md"
    recent = tmp_path / "sessions" / "index-recent.md"
    assert rebuild(tmp_path)[0]
    source_bytes = {first: first.read_bytes(), second: second.read_bytes()}
    index_bytes = {index: index.read_bytes(), recent: recent.read_bytes()}
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    real_rename = session_archive.os.rename
    calls = 0

    def fail_second_rename(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second-move failure")
        real_rename(source, destination)

    monkeypatch.setattr(session_archive.os, "rename", fail_second_rename)

    with pytest.raises(RuntimeError, match="rollback verified clean"):
        apply_archive(moves, tmp_path)

    assert {path: path.read_bytes() for path in source_bytes} == source_bytes
    assert {path: path.read_bytes() for path in index_bytes} == index_bytes
    assert rebuild(tmp_path, check=True) == (True, "session indexes current")
    assert not (tmp_path / "sessions" / "archive").exists()


@pytest.mark.parametrize("failure_point", ["rebuild", "verification"])
def test_post_move_index_failure_restores_sources_and_exact_current_indexes(tmp_path: Path, monkeypatch, failure_point: str):
    import memento_tattoo.session_archive as session_archive

    source = _write_session(tmp_path, "sess_old", "2026-06-01 10:00")
    original = source.read_bytes()
    index = tmp_path / "sessions" / "index.md"
    recent = tmp_path / "sessions" / "index-recent.md"
    assert rebuild(tmp_path)[0]
    index_bytes = {index: index.read_bytes(), recent: recent.read_bytes()}
    calls = 0
    real_rebuild_locked = session_archive._rebuild_locked

    def failing_rebuild_locked(root, *, check=False):
        nonlocal calls
        calls += 1
        if failure_point == "rebuild" and calls == 1:
            index.write_bytes(b"partial rebuilt index\n")
            recent.write_bytes(b"partial rebuilt recent\n")
            return False, "injected rebuild failure"
        if failure_point == "verification" and calls == 2 and check:
            return False, "injected verification failure"
        return real_rebuild_locked(root, check=check)

    monkeypatch.setattr(session_archive, "_rebuild_locked", failing_rebuild_locked)
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))

    with pytest.raises(RuntimeError, match="rollback verified clean"):
        apply_archive(moves, tmp_path)

    assert calls == (2 if failure_point == "rebuild" else 3)
    assert source.read_bytes() == original
    assert not (tmp_path / "sessions" / "archive").exists()
    assert {path: path.read_bytes() for path in index_bytes} == index_bytes
    assert rebuild(tmp_path, check=True) == (True, "session indexes current")


def test_stale_index_snapshot_is_preserved_and_rollback_reports_incomplete(tmp_path: Path, monkeypatch):
    import memento_tattoo.session_archive as session_archive

    first = _write_session(tmp_path, "sess_first", "2026-06-01 10:00")
    second = _write_session(tmp_path, "sess_second", "2026-06-02 10:00")
    index = tmp_path / "sessions" / "index.md"
    recent = tmp_path / "sessions" / "index-recent.md"
    index.write_bytes(b"pre-existing stale index\n")
    recent.write_bytes(b"pre-existing stale recent\n")
    index_bytes = {index: index.read_bytes(), recent: recent.read_bytes()}
    source_bytes = {first: first.read_bytes(), second: second.read_bytes()}
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    real_rename = session_archive.os.rename
    calls = 0

    def fail_second_rename(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second-move failure")
        real_rename(source, destination)

    monkeypatch.setattr(session_archive.os, "rename", fail_second_rename)

    with pytest.raises(RuntimeError, match="rollback incomplete: .*stale indexes"):
        apply_archive(moves, tmp_path)

    assert {path: path.read_bytes() for path in source_bytes} == source_bytes
    assert {path: path.read_bytes() for path in index_bytes} == index_bytes
    assert rebuild(tmp_path, check=True)[0] is False


def test_absent_index_snapshot_is_preserved_and_rollback_reports_incomplete(tmp_path: Path, monkeypatch):
    import memento_tattoo.session_archive as session_archive

    source = _write_session(tmp_path, "sess_old", "2026-06-01 10:00")
    source_bytes = source.read_bytes()
    index = tmp_path / "sessions" / "index.md"
    recent = tmp_path / "sessions" / "index-recent.md"
    real_rebuild_locked = session_archive._rebuild_locked
    calls = 0

    def fail_verification(root, *, check=False):
        nonlocal calls
        calls += 1
        if calls == 2 and check:
            return False, "injected verification failure"
        return real_rebuild_locked(root, check=check)

    monkeypatch.setattr(session_archive, "_rebuild_locked", fail_verification)
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))

    with pytest.raises(RuntimeError, match="rollback incomplete: .*stale indexes"):
        apply_archive(moves, tmp_path)

    assert calls == 3
    assert source.read_bytes() == source_bytes
    assert not index.exists()
    assert not recent.exists()
    assert rebuild(tmp_path, check=True)[0] is False


def test_rollback_failure_is_reported_as_incomplete(tmp_path: Path, monkeypatch):
    import memento_tattoo.session_archive as session_archive

    _write_session(tmp_path, "sess_first", "2026-06-01 10:00")
    _write_session(tmp_path, "sess_second", "2026-06-02 10:00")
    assert rebuild(tmp_path)[0]
    index = tmp_path / "sessions" / "index.md"
    recent = tmp_path / "sessions" / "index-recent.md"
    index_bytes = {index: index.read_bytes(), recent: recent.read_bytes()}
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    real_rename = session_archive.os.rename
    calls = 0

    def fail_move_and_rollback(source, destination):
        nonlocal calls
        calls += 1
        if calls in {2, 3}:
            raise OSError(f"injected rename failure {calls}")
        real_rename(source, destination)

    monkeypatch.setattr(session_archive.os, "rename", fail_move_and_rollback)

    with pytest.raises(RuntimeError, match="rollback incomplete") as exc:
        apply_archive(moves, tmp_path)

    assert "rollback verified clean" not in str(exc.value)
    assert {path: path.read_bytes() for path in index_bytes} == index_bytes
    assert rebuild(tmp_path, check=True) == (True, "session indexes current")
