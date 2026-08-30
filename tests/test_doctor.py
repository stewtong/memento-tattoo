from pathlib import Path

from memento_tattoo.doctor import (
    RECOMMENDED_ALIAS_COVERAGE_PERCENT,
    RECOMMENDED_TATTOO_BYTES,
    RECOMMENDED_TATTOO_COUNT,
    RECOMMENDED_TATTOO_LENGTH,
    run_doctor,
)
from memento_tattoo.retention import append_retention_event


# --- helpers for tattoo-audit doctor check ---

def _seed_session(root: Path, sess: str, when: str) -> None:
    sessions = root / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{sess}.md").write_text(
        f"---\n[{sess} | {when} | codex | test | low]\n"
        "Accomplished: x\nStarted: none\nPending: none\nInsights: none\nFiles: none\n---\n",
        encoding="utf-8",
    )


def _seed_tattoos(root: Path, body: str) -> None:
    (root / "tattoos.md").write_text("# Tattoos\n\n" + body, encoding="utf-8")


def _note(note_id: str, aliases: str = "") -> str:
    return (
        f"<!-- delta:{note_id} -->\n"
        "Situation: diagnostic coverage\n"
        "Note: retain parsed evidence\n"
        f"aliases: {aliases}\n"
    )


def _tattoos(*texts: str) -> str:
    return "\n".join(
        f"<!-- delta:sess_{index}.tattoo.{index:08d} -->\n- {text}\n"
        for index, text in enumerate(texts, start=1)
    )


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
    assert "retention health 0.00" in output
    assert "not prevention/application" in output


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


def test_doctor_warns_on_flagged_tattoos(tmp_path: Path):
    """A tattoo with an old ts= marker produces a WARN (not fail) in doctor output."""
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    # Anchor session is recent; tattoo marker is old -> flagged by audit_tattoos.
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_old.tattoo.aaaaaaaa agent=codex ts=2026-01-01T00:00:00Z -->\n"
        "- Old tattoo bullet.\n",
    )

    ok, output = run_doctor(tmp_path)

    # Must remain True (warn, not fail)
    assert ok is True
    # Warning line must report the count and point to tattoo-audit
    assert "tattoo-lifecycle" in output
    assert "tattoo-audit" in output
    assert "1 tattoo" in output


def test_doctor_no_tattoo_lifecycle_warn_when_tattoos_md_absent(tmp_path: Path):
    """When tattoos.md does not exist the tattoo-lifecycle check emits nothing."""
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    # No tattoos.md seeded; sessions dir also absent.

    ok, output = run_doctor(tmp_path)

    assert "tattoo-lifecycle" not in output


def test_doctor_warns_when_repeat_rate_is_low_at_volume(tmp_path: Path):
    (tmp_path / "notes.md").write_text("Situation: x\nNote: y\n", encoding="utf-8")
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    for index in range(50):
        append_retention_event({"decision": "new", "note_id": f"sess_{index}.note.11111111"}, root=tmp_path)

    ok, output = run_doctor(tmp_path)

    assert ok is True
    assert "retention health 0.00" in output
    assert "retention health under 0.05 at volume" in output


def test_doctor_recall_probe_miss_fails(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_a.note.aaaaaaaa -->\n"
        "Situation: proofreading public prose\n"
        "Note: scan for banned punctuation\n",
        encoding="utf-8",
    )
    (tmp_path / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    append_retention_event({"decision": "new", "note_id": "sess_a.note.aaaaaaaa"}, root=tmp_path)
    (tmp_path / ".recall_probes.json").write_text(
        '[{"query": "GPU quota planning", "expect": "sess_a.note.aaaaaaaa", "top": 1}]\n',
        encoding="utf-8",
    )

    ok, output = run_doctor(tmp_path)

    assert ok is False
    assert "recall-probes" in output
    assert "not in top-1" in output


def test_recommended_diagnostic_thresholds_are_named():
    assert RECOMMENDED_ALIAS_COVERAGE_PERCENT == 60
    assert RECOMMENDED_TATTOO_COUNT == 25
    assert RECOMMENDED_TATTOO_BYTES == 7_168
    assert RECOMMENDED_TATTOO_LENGTH == 300


def test_doctor_reports_hot_and_archive_alias_coverage_separately(tmp_path: Path):
    (tmp_path / "notes.md").write_text(_note("sess_hot.note.11111111", "hot trigger"), encoding="utf-8")
    (tmp_path / "notes_archive.md").write_text(
        "<!-- not-a-delta -->\nnot a parsed note record\n"
        + _note("sess_cold1.note.22222222", "archive trigger")
        + _note("sess_cold2.note.33333333"),
        encoding="utf-8",
    )
    _seed_tattoos(tmp_path, "")

    _, output = run_doctor(tmp_path)

    assert "hot 1/1 aliased; archive 1/2 aliased" in output
    assert "archive coverage below 60%" in output


def test_alias_coverage_boundary_override_disable_and_empty_archive(tmp_path: Path):
    (tmp_path / "notes.md").write_text(_note("sess_hot.note.11111111"), encoding="utf-8")
    _seed_tattoos(tmp_path, "")

    _, empty_output = run_doctor(tmp_path)
    assert "archive 0/0 aliased" in empty_output
    assert "archive coverage below" not in empty_output

    (tmp_path / "notes_archive.md").write_text(
        "".join(
            _note(f"sess_{index}.note.{index:08d}", "trigger" if index <= 3 else "")
            for index in range(1, 6)
        ),
        encoding="utf-8",
    )
    _, at_boundary = run_doctor(tmp_path)
    _, overridden = run_doctor(tmp_path, alias_coverage_warn=61)
    _, disabled = run_doctor(tmp_path, alias_coverage_warn=0)

    assert "archive coverage below" not in at_boundary
    assert "archive coverage below 61%" in overridden
    assert "archive 3/5 aliased" in disabled
    assert "archive coverage below" not in disabled


def test_tattoo_count_boundary_override_and_disable(tmp_path: Path):
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    _seed_tattoos(tmp_path, _tattoos(*(["x"] * 3)))

    _, at_boundary = run_doctor(tmp_path, tattoo_count_warn=3, tattoo_bytes_warn=0, tattoo_length_warn=0)
    _, over = run_doctor(tmp_path, tattoo_count_warn=2, tattoo_bytes_warn=0, tattoo_length_warn=0)
    _, disabled = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=0, tattoo_length_warn=0)

    assert "3 tattoos" in at_boundary and "count over" not in at_boundary
    assert "count over 2" in over
    assert "3 tattoos" in disabled and "count over" not in disabled


def test_tattoo_byte_boundary_override_disable_and_multibyte_measurement(tmp_path: Path):
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    _seed_tattoos(tmp_path, _tattoos("é"))

    _, at_boundary = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=2, tattoo_length_warn=0)
    _, over = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=1, tattoo_length_warn=0)
    _, disabled = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=0, tattoo_length_warn=0)

    assert "2 UTF-8 bytes" in at_boundary and "bytes over" not in at_boundary
    assert "bytes over 1" in over
    assert "2 UTF-8 bytes" in disabled and "bytes over" not in disabled


def test_tattoo_length_boundary_override_disable_and_bounded_sample(tmp_path: Path):
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    _seed_tattoos(tmp_path, _tattoos("abc", "defg", "hijkl", "mnopqr", "stuvwxy"))

    _, at_boundary = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=0, tattoo_length_warn=7)
    _, over = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=0, tattoo_length_warn=3)
    _, disabled = run_doctor(tmp_path, tattoo_count_warn=0, tattoo_bytes_warn=0, tattoo_length_warn=0)

    assert "0 over 7 characters" in at_boundary and "length over" not in at_boundary
    assert "4 over 3 characters" in over and over.count("ch:") == 3
    assert "0 over 300 characters" in disabled and "length over" not in disabled


def test_tattoo_pressure_warnings_coexist_without_mutation(tmp_path: Path):
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    _seed_tattoos(tmp_path, _tattoos("éééé", "another long tattoo"))
    firing = tmp_path / "tattoo_firing.json"
    firing.write_text('{"sess_1": 2}\n', encoding="utf-8")
    tattoos_before = (tmp_path / "tattoos.md").read_bytes()
    firing_before = firing.read_bytes()

    _, output = run_doctor(tmp_path, tattoo_count_warn=1, tattoo_bytes_warn=7, tattoo_length_warn=3)

    assert "count over 1" in output
    assert "bytes over 7" in output
    assert "length over 3" in output
    assert "run tattoo-audit" in output
    assert (tmp_path / "tattoos.md").read_bytes() == tattoos_before
    assert firing.read_bytes() == firing_before
