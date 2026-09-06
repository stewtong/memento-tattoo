from __future__ import annotations

import json
import os
from pathlib import Path

from memento_tattoo.doctor import run_doctor
from memento_tattoo.garden import build_digest
from memento_tattoo.registry import archive_registry_conflicts, conflict_archive_candidates, drain
from memento_tattoo.retention import read_retention_events, rotate_retention_log
from memento_tattoo.session_store import render_session_block, write_session_block
from memento_tattoo.tattoo_firing import effective_tattoo_firing_counts


def _block(sess: str, text: str) -> str:
    return render_session_block(sess, date="2026-08-01", agent="test", topics=["x"], significance="low", accomplished=text, started="none", pending="none", insights="none", files=[])


def test_registry_malformed_delta_fails_without_mutation_or_loop(tmp_path: Path):
    queue = tmp_path / "_queue"
    queue.mkdir()
    malformed = queue / "bad.registry.md"
    malformed.write_text("not a delta\n", encoding="utf-8")
    conflicts = queue / "conflicts"
    conflicts.mkdir()
    old_conflict = conflicts / "old.registry.md"
    old_conflict.write_text("preserve on failure\n", encoding="utf-8")
    os.utime(old_conflict, (100, 100))
    result = drain(tmp_path)
    assert not result.ok
    assert malformed.exists()
    assert old_conflict.exists()
    assert not (conflicts / "archive/old.registry.md").exists()
    assert not (tmp_path / "registry.md").exists()


def test_session_id_collision_across_archive_is_rejected(tmp_path: Path):
    archive = tmp_path / "sessions/archive"
    archive.mkdir(parents=True)
    (archive / "sess_old.md").write_text(_block("sess_same", "old"), encoding="utf-8")
    try:
        write_session_block(tmp_path, _block("sess_same", "new"), "sess_same")
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected cross-store collision rejection")


def test_garden_attributes_repair_to_cover_note_and_bounds_output(tmp_path: Path):
    events = []
    for index in range(12):
        events.append({"decision": "existing-missed", "decision_source": "author", "note_id": f"new-{index}", "cover_note_id": f"cover-{index}"})
    (tmp_path / "retention_log.jsonl").write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    digest = build_digest(root=tmp_path, today="2026-08-28", limit=8)
    assert "cover-0" in digest
    assert "new-0:" not in digest
    assert "12 total, showing 8" in digest


def test_durable_tattoo_citations_override_stale_counter(tmp_path: Path):
    (tmp_path / "sessions").mkdir()
    tattoo_id = "sess_abcd.tattoo.1234"
    (tmp_path / "sessions/sess_ref.md").write_text(f"Insights: used [[{tattoo_id}]]\n", encoding="utf-8")
    (tmp_path / "tattoo_firing.json").write_text("{}\n", encoding="utf-8")
    assert effective_tattoo_firing_counts(tmp_path)[tattoo_id]["count"] == 1


def test_retention_rotation_is_byte_bounded_and_lossless(tmp_path: Path):
    hot = tmp_path / "retention_log.jsonl"
    hot.write_text("\n".join(json.dumps({"i": i, "pad": "x" * 500}) for i in range(500)) + "\n", encoding="utf-8")
    before = read_retention_events(root=tmp_path)
    moved = rotate_retention_log(root=tmp_path, keep=500)
    assert moved > 0
    assert hot.stat().st_size <= 128 * 1024
    after = read_retention_events(root=tmp_path)
    assert len({event["event_id"] for event in after}) == len(before)
    assert [{key: value for key, value in event.items() if key != "event_id"} for event in after] == before


def test_doctor_fails_on_corrupt_tattoo_counter(tmp_path: Path):
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("", encoding="utf-8")
    (tmp_path / "tattoo_firing.json").write_text("{broken", encoding="utf-8")
    ok, output = run_doctor(tmp_path)
    assert not ok
    assert "tattoo-firing" in output


def test_registry_conflicts_are_age_and_count_bounded_without_loss(tmp_path: Path):
    conflicts = tmp_path / "_queue/conflicts"
    conflicts.mkdir(parents=True)
    for index in range(5):
        path = conflicts / f"{index}.registry.md"
        path.write_text(f"{index}\n", encoding="utf-8")
        os.utime(path, (100 + index, 100 + index))
    candidates = conflict_archive_candidates(tmp_path, days=100000, max_hot=3)
    assert len(candidates) == 2
    assert archive_registry_conflicts(tmp_path, days=100000, max_hot=3) == 2
    hot = list(conflicts.glob("*.registry.md"))
    cold = list((conflicts / "archive").glob("*.registry.md"))
    assert len(hot) == 3 and len(cold) == 2
