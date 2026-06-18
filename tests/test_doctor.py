from pathlib import Path

from memento_tattoo.doctor import run_doctor
from memento_tattoo.retention import append_retention_event


def test_doctor_warns_on_empty_root(tmp_path: Path):
    ok, output = run_doctor(tmp_path)

    assert ok is False
    assert "notes.md missing" in output


def test_doctor_passes_minimal_valid_root(tmp_path: Path):
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (tmp_path / "project.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)

    ok, output = run_doctor(tmp_path)

    assert ok is True
    assert "retention events: 1" in output


def test_doctor_does_not_require_legacy_project_file_when_project_memory_is_checked(tmp_path: Path):
    root = tmp_path / ".memento"
    root.mkdir()
    (root / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (root / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=root)
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text("# Project Memory\n\n## Key Decisions\n\n## State\n", encoding="utf-8")

    ok, output = run_doctor(root, projects=[project])

    assert ok is True
    assert "project.md missing" in output
    assert "memory.md present" in output


def test_doctor_accepts_project_memory_only_root_when_project_is_checked(tmp_path: Path):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text("# Project Memory\n\n## Key Decisions\n\n## State\n", encoding="utf-8")

    ok, output = run_doctor(root, projects=[project])

    assert ok is True
    assert "notes.md missing" in output
    assert "tattoos.md missing" in output
    assert "memory.md present" in output


def test_doctor_checks_adjacent_project_memory(tmp_path: Path):
    root = tmp_path / ".memento"
    root.mkdir()
    (root / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (root / "project.md").write_text("# Project\n", encoding="utf-8")
    (root / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=root)
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text("# Project Memory\n\n## Key Decisions\n\n## State\n", encoding="utf-8")

    ok, output = run_doctor(root, projects=[project])

    assert ok is True
    assert "project-memory" in output
    assert "memory.md present" in output


def test_doctor_fails_when_requested_project_memory_is_missing(tmp_path: Path):
    root = tmp_path / ".memento"
    root.mkdir()
    (root / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (root / "project.md").write_text("# Project\n", encoding="utf-8")
    (root / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=root)
    project = tmp_path / "project"

    ok, output = run_doctor(root, projects=[project])

    assert ok is False
    assert "project-memory" in output
    assert "memory.md missing" in output


def test_doctor_warns_on_stale_session_index(tmp_path: Path):
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_a111.md").write_text(
        "---\n[sess_a111 | 2026-06-17 10:00 | codex | docs | low]\nAccomplished: A.\n---\n",
        encoding="utf-8",
    )
    (sessions / "index.md").write_text("# stale\n", encoding="utf-8")

    ok, output = run_doctor(tmp_path)

    assert ok is True
    assert "session-index" in output
    assert "stale" in output


def test_doctor_warns_on_expired_reserved_ids(tmp_path: Path):
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    (tmp_path / ".reserved_ids").write_text("sess_bbbb 2000-01-01T00:00:00Z\n", encoding="utf-8")

    ok, output = run_doctor(tmp_path)

    assert ok is True
    assert "reserved-ids" in output
    assert "expired" in output


def test_doctor_warns_on_pending_registry_queue(tmp_path: Path):
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    queue = tmp_path / "_queue"
    queue.mkdir()
    (queue / "20260617T000000Z.sess_abcd.demo.11111111.registry.md").write_text(
        "<!-- registry-delta sess=sess_abcd action=update slug=demo agent=codex ts=2026-06-17T00:00:00Z -->\n"
        "- Demo - demo/ - active\n",
        encoding="utf-8",
    )

    ok, output = run_doctor(tmp_path)

    assert ok is True
    assert "registry-queue" in output
    assert "pending" in output


def test_doctor_warns_on_registry_conflicts(tmp_path: Path):
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    conflicts = tmp_path / "_queue" / "conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "loser.registry.md").write_text("x\n", encoding="utf-8")

    ok, output = run_doctor(tmp_path)

    assert ok is True
    assert "registry-conflicts" in output
    assert "1" in output
