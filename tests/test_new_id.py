import multiprocessing
import re
from pathlib import Path

import pytest

from memento_tattoo import new_id
from memento_tattoo.new_id import generate_session_id, prune_reservations, taken_session_ids


ID_RE = re.compile(r"^sess_[0-9a-f]{4}$")


def _seed_sessions(root: Path, ids: list[str]) -> None:
    sessions = root / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        (sessions / f"{sid}.md").write_text(
            f"---\n[{sid} | 2026-06-17 10:00 | codex | test | low]\nAccomplished: x\n---\n",
            encoding="utf-8",
        )


def test_generated_id_is_well_formed_and_free(tmp_path: Path):
    _seed_sessions(tmp_path, ["sess_aaaa", "sess_bbbb"])

    sid = generate_session_id(tmp_path)

    assert ID_RE.match(sid)
    assert sid not in {"sess_aaaa", "sess_bbbb"}


def test_taken_ids_include_hot_archive_and_reservations(tmp_path: Path):
    _seed_sessions(tmp_path, ["sess_1111"])
    archive = tmp_path / "sessions" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "sess_2222.md").write_text(
        "---\n[sess_2222 | 2026-06-01 09:00 | claude | test | low]\nAccomplished: y\n---\n",
        encoding="utf-8",
    )
    (tmp_path / ".reserved_ids").write_text("sess_3333 2999-01-01T00:00:00Z\n", encoding="utf-8")

    assert {"sess_1111", "sess_2222", "sess_3333"} <= taken_session_ids(tmp_path)


def test_collision_is_retried(tmp_path: Path, monkeypatch):
    _seed_sessions(tmp_path, ["sess_dead"])
    draws = iter(["dead", "beef"])
    monkeypatch.setattr(new_id.secrets, "token_hex", lambda n: next(draws))

    assert generate_session_id(tmp_path) == "sess_beef"


def test_drawn_id_is_reserved_before_file_written(tmp_path: Path):
    (tmp_path / "sessions").mkdir(parents=True)

    sid = generate_session_id(tmp_path)

    assert sid in taken_session_ids(tmp_path)
    assert generate_session_id(tmp_path) != sid


def test_forced_process_collision_reserves_only_once(tmp_path: Path):
    if multiprocessing.get_start_method(allow_none=True) not in (None, "fork"):
        pytest.skip("forced collision test requires fork-compatible multiprocessing")
    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(2)
    queue = ctx.Queue()

    first = ctx.Process(target=_reserve_with_draws, args=(tmp_path, barrier, queue, ["dead", "beef"]))
    second = ctx.Process(target=_reserve_with_draws, args=(tmp_path, barrier, queue, ["dead", "cafe"]))
    first.start()
    second.start()
    first.join(10)
    second.join(10)

    assert first.exitcode == 0
    assert second.exitcode == 0
    returned = {queue.get(timeout=1), queue.get(timeout=1)}
    assert len(returned) == 2
    assert returned <= taken_session_ids(tmp_path)
    assert not any((tmp_path / "sessions" / f"{sid}.md").exists() for sid in returned)


def _reserve_with_draws(root: Path, barrier, queue, draws: list[str]) -> None:
    from memento_tattoo import new_id as new_id_module

    draw_iter = iter(draws)
    new_id_module.secrets.token_hex = lambda n: next(draw_iter)
    barrier.wait()
    queue.put(new_id_module.generate_session_id(root))


def test_prune_clears_written_and_expired_reservations(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "sess_aaaa.md").write_text(
        "---\n[sess_aaaa | 2026-06-17 10:00 | codex | t | low]\nAccomplished: x\n---\n",
        encoding="utf-8",
    )
    (tmp_path / ".reserved_ids").write_text(
        "sess_aaaa 2026-06-17T10:00:00Z\n"
        "sess_bbbb 2000-01-01T00:00:00Z\n"
        "sess_cccc 2999-01-01T00:00:00Z\n",
        encoding="utf-8",
    )

    assert prune_reservations(tmp_path) == 2
    remaining = (tmp_path / ".reserved_ids").read_text(encoding="utf-8")
    assert "sess_aaaa" not in remaining
    assert "sess_bbbb" not in remaining
    assert "sess_cccc" in remaining
