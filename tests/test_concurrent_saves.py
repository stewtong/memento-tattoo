import multiprocessing
from datetime import date
from pathlib import Path

import pytest

from memento_tattoo.registry import drain
from memento_tattoo.rebuild import rebuild
from memento_tattoo.session_archive import apply_archive, archive_candidates
from memento_tattoo.session_store import render_session_block


def test_process_concurrent_saves_preserve_all_surfaces(tmp_path: Path):
    ctx = _fork_context()
    workers = 6
    barrier = ctx.Barrier(workers)
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_save_worker, args=(tmp_path, barrier, queue, index))
        for index in range(workers)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(15)

    assert all(process.exitcode == 0 for process in processes)
    sessions = [queue.get(timeout=1) for _ in range(workers)]
    final_drain = drain(tmp_path)
    rebuilt, rebuild_output = rebuild(tmp_path)

    assert not final_drain.skipped
    assert rebuilt, rebuild_output
    assert len(set(sessions)) == workers
    notes = (tmp_path / "notes.md").read_text(encoding="utf-8")
    tattoos = (tmp_path / "tattoos.md").read_text(encoding="utf-8")
    registry = (tmp_path / "registry.md").read_text(encoding="utf-8")
    index = (tmp_path / "sessions" / "index.md").read_text(encoding="utf-8")
    for worker_index, sid in enumerate(sessions):
        assert sid in index
        assert f"worker {worker_index} note" in notes
        assert f"worker {worker_index} tattoo" in tattoos
        assert f"worker-{worker_index}" in registry


def test_process_concurrent_project_edits_preserve_all_bodies(tmp_path: Path):
    ctx = _fork_context()
    workers = 4
    barrier = ctx.Barrier(workers)
    processes = [
        ctx.Process(target=_project_worker, args=(tmp_path, barrier, index))
        for index in range(workers)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(15)

    assert all(process.exitcode == 0 for process in processes)
    text = (tmp_path / "project" / "memory.md").read_text(encoding="utf-8")
    for index in range(workers):
        assert f"worker {index} project state" in text


def test_archive_rollback_excludes_compliant_writer_until_indexes_are_verified(tmp_path: Path, monkeypatch):
    import memento_tattoo.session_archive as session_archive

    ctx = _fork_context()
    old_path = tmp_path / "sessions" / "sess_old.md"
    old_path.parent.mkdir(parents=True)
    old_path.write_text(_session_block("sess_old", "2026-06-01 10:00"), encoding="utf-8")
    assert rebuild(tmp_path)[0]
    moves = archive_candidates(tmp_path, days=10, today=date(2026, 6, 30))
    verification_reached = ctx.Event()
    allow_verification_failure = ctx.Event()
    writer_blocked = ctx.Event()
    queue = ctx.Queue()
    real_rebuild_locked = session_archive._rebuild_locked
    calls = 0

    def fail_verification_after_writer_attempt(root, *, check=False):
        nonlocal calls
        calls += 1
        if calls == 2 and check:
            verification_reached.set()
            if not allow_verification_failure.wait(10):
                raise RuntimeError("test did not release archive verification")
            return False, "injected verification failure"
        return real_rebuild_locked(root, check=check)

    monkeypatch.setattr(session_archive, "_rebuild_locked", fail_verification_after_writer_attempt)
    archive_process = ctx.Process(target=_archive_failure_worker, args=(tmp_path, moves, queue))
    archive_process.start()
    assert verification_reached.wait(5)

    writer_process = ctx.Process(target=_archive_interleaving_writer, args=(tmp_path, writer_blocked, queue))
    writer_process.start()
    assert writer_blocked.wait(5)
    assert not (tmp_path / "sessions" / "sess_writer.md").exists()

    allow_verification_failure.set()
    archive_process.join(10)
    writer_process.join(10)

    assert archive_process.exitcode == 0
    assert writer_process.exitcode == 0
    messages = [queue.get(timeout=1) for _ in range(3)]
    archive_messages = [message for kind, message in messages if kind == "archive"]
    assert len(archive_messages) == 1
    assert "rollback verified clean" in archive_messages[0]
    assert {kind for kind, _ in messages} == {"archive", "writer-commit", "writer-rebuild"}
    assert old_path.exists()
    assert (tmp_path / "sessions" / "sess_writer.md").exists()
    assert rebuild(tmp_path, check=True) == (True, "session indexes current")
    index = (tmp_path / "sessions" / "index.md").read_text(encoding="utf-8")
    assert "sess_old" in index
    assert "sess_writer" in index


def _fork_context():
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        pytest.skip("concurrency tests require fork-compatible multiprocessing")


def _save_worker(root: Path, barrier, queue, index: int) -> None:
    from memento_tattoo.new_id import generate_session_id
    from memento_tattoo.registry import drain, registry_queue
    from memento_tattoo.session_store import render_session_block, write_session_block
    from memento_tattoo.write_through import note_add, tattoo_add

    barrier.wait()
    sid = generate_session_id(root)
    block = render_session_block(
        sid,
        date=f"2026-06-17 18:{index:02d}",
        agent=f"worker-{index}",
        topics=["concurrency"],
        significance="medium",
        accomplished=f"worker {index} saved.",
        started="none.",
        pending="none.",
        insights="none.",
        files=[],
    )
    write_session_block(root, block, sid)
    note_add(f"Situation: worker {index} note\nNote: preserve concurrent writes", sess=sid, root=root, kind="seed", agent=f"worker-{index}")
    tattoo_add(f"worker {index} tattoo", sess=sid, root=root, agent=f"worker-{index}")
    registry_queue(sid, "update", f"worker-{index}", f"- worker-{index} - worker/{index} - active", root, agent=f"worker-{index}")
    drain(root, timeout=0.1)
    queue.put(sid)


def _project_worker(root: Path, barrier, index: int) -> None:
    from memento_tattoo.write_through import project_edit

    flow_start = "2026-06-17T00:00:00Z"
    barrier.wait()
    project_edit(
        f"- worker {index} project state",
        sess=f"sess_p{index:03d}",
        root=root / ".memento",
        project=root / "project",
        section="## State",
        flow_start=flow_start,
        agent=f"worker-{index}",
    )


def _session_block(sess: str, session_date: str) -> str:
    return render_session_block(
        sess,
        date=session_date,
        agent="codex",
        topics=["concurrency"],
        significance="medium",
        accomplished=f"Recorded {sess}.",
        started="none.",
        pending="none.",
        insights="none.",
        files=[],
    )


def _archive_failure_worker(root: Path, moves, queue) -> None:
    try:
        apply_archive(moves, root)
    except RuntimeError as exc:
        queue.put(("archive", str(exc)))
        return
    queue.put(("archive", "unexpected success"))


def _archive_interleaving_writer(root: Path, blocked, queue) -> None:
    from memento_tattoo.lock import LockTimeout, memory_lock
    from memento_tattoo.rebuild import rebuild
    from memento_tattoo.session_store import write_session_block

    try:
        with memory_lock(root, timeout=0.2):
            queue.put(("writer-lock", "unexpected acquisition"))
    except LockTimeout:
        blocked.set()

    block = _session_block("sess_writer", "2026-06-30 12:00")
    path = write_session_block(root, block, "sess_writer")
    queue.put(("writer-commit", str(path)))
    ok, output = rebuild(root)
    if not ok:
        raise RuntimeError(output)
    queue.put(("writer-rebuild", output))
