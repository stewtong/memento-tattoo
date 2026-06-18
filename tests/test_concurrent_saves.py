import multiprocessing
from pathlib import Path

import pytest

from memento_tattoo.registry import drain
from memento_tattoo.rebuild import rebuild


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
