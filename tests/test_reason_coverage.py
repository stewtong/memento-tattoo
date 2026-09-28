from pathlib import Path

import pytest

from memento_tattoo.cli import main
from memento_tattoo.doctor import has_reason_clause, run_doctor, why_coverage_summary


HOT_NOTES = (
    "<!-- delta:sess_a.note.11111111 -->\n"
    "Situation: renaming a public function\n"
    "Note: search other packages for callers.\n"
    "Why: CI runs only the changed package's tests.\n"
    "aliases: rename, callers\n\n"
    "<!-- delta:sess_a.note.22222222 -->\n"
    "Situation: editing generated clients\n"
    "Note: edit the schema, not the output.\n"
    "aliases: codegen\n\n"
    "<!-- delta:sess_a.note.33333333 -->\n"
    "Situation: empty reason\n"
    "Note: a Why field with no text does not count.\n"
    "Why:\n"
    "aliases: blank\n"
)
ARCHIVE_NOTES = (
    "<!-- delta:sess_old.note.44444444 -->\n"
    "Situation: older lesson without a reason\n"
    "Note: written before Why existed.\n"
    "aliases: legacy\n"
)
TATTOOS = (
    "# Tattoos\n\n"
    "<!-- delta:sess_a.tattoo.55555555 -->\n"
    "- Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.\n\n"
    "<!-- delta:sess_a.tattoo.66666666 -->\n"
    "- Keep tattoos scarce.\n"
)


def _mixed_root(tmp_path: Path) -> Path:
    root = tmp_path / "memento"
    root.mkdir()
    (root / "notes.md").write_text(HOT_NOTES, encoding="utf-8")
    (root / "notes_archive.md").write_text(ARCHIVE_NOTES, encoding="utf-8")
    (root / "tattoos.md").write_text(TATTOOS, encoding="utf-8")
    return root


def test_why_coverage_counts_hot_and_archive_records_separately(tmp_path: Path):
    summary = why_coverage_summary(_mixed_root(tmp_path))

    assert (summary["hot"].with_why, summary["hot"].total) == (1, 3)
    assert (summary["archive"].with_why, summary["archive"].total) == (0, 1)


def test_doctor_reports_reason_coverage_without_warning_by_default(tmp_path: Path):
    ok, output = run_doctor(_mixed_root(tmp_path))

    assert ok is True, output
    assert "PASS  why-coverage: hot 1/3 with Why; archive 0/1 with Why" in output
    assert "PASS  tattoo-reasons: 1/2 with a reason clause" in output


def test_doctor_warns_below_opt_in_thresholds(tmp_path: Path):
    ok, output = run_doctor(_mixed_root(tmp_path), why_coverage_warn=60, tattoo_reason_warn=75)

    assert ok is True, output
    assert "WARN  why-coverage: hot 1/3 with Why; archive 0/1 with Why; hot and archive below 60% review threshold" in output
    assert "WARN  tattoo-reasons: 1/2 with a reason clause; below 75% review threshold" in output


def test_doctor_threshold_passes_when_coverage_meets_it(tmp_path: Path):
    ok, output = run_doctor(_mixed_root(tmp_path), why_coverage_warn=30, tattoo_reason_warn=50)

    assert "PASS  tattoo-reasons: 1/2 with a reason clause" in output
    assert "WARN  why-coverage" in output and "archive below 30%" in output and "hot and archive" not in output


def test_store_without_why_fields_produces_no_errors(tmp_path: Path):
    root = tmp_path / "memento"
    root.mkdir()
    (root / "notes.md").write_text(
        "<!-- delta:sess_a.note.11111111 -->\nSituation: x\nNote: y\naliases: z\n", encoding="utf-8"
    )
    (root / "tattoos.md").write_text("# Tattoos\n\n<!-- delta:sess_a.tattoo.1 -->\n- Keep tattoos scarce.\n", encoding="utf-8")

    ok, output = run_doctor(root)

    assert ok is True, output
    assert "PASS  why-coverage: hot 0/1 with Why; archive 0/0 with Why" in output
    assert "PASS  tattoo-reasons: 0/1 with a reason clause" in output
    assert "FAIL" not in output


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Before X, do Y; Z would break otherwise.", True),
        ("Do Y before X.", False),
        ("; reason only", False),
        ("Action only;", False),
        ("Action only; .", False),
    ],
)
def test_reason_clause_shape(text: str, expected: bool):
    assert has_reason_clause(text) is expected


def test_cli_passes_reason_thresholds(tmp_path: Path, capsys):
    root = _mixed_root(tmp_path)

    assert main(["--root", str(root), "doctor", "--why-coverage-warn", "50", "--tattoo-reason-warn", "90"]) == 0
    out = capsys.readouterr().out
    assert "WARN  why-coverage" in out
    assert "WARN  tattoo-reasons" in out


def test_doctor_accepts_current_state_heading_for_project_memory(tmp_path: Path):
    root = _mixed_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text("# Project Memory\n\n## Key Decisions\n\n## Current state\n", encoding="utf-8")

    ok, output = run_doctor(root, projects=[project])

    assert ok is True, output
    assert "PASS  project-memory: memory.md present for project" in output


def test_doctor_still_rejects_project_memory_without_a_state_section(tmp_path: Path):
    root = _mixed_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text("# Project Memory\n\n## Key Decisions\n\nCurrent state is prose.\n", encoding="utf-8")

    ok, output = run_doctor(root, projects=[project])

    assert ok is False
    assert "missing required sections" in output


def test_why_field_survives_note_add_and_note_amend(tmp_path: Path):
    from memento_tattoo.entries import amend_note, resolve_entry
    from memento_tattoo.write_through import note_add

    root = tmp_path / "memento"
    _, marker = note_add(
        "Situation: renaming a public function\nNote: search callers.\nWhy: CI runs only the changed package's tests.\naliases: rename",
        sess="sess_x",
        root=root,
        kind="correction",
    )
    note_id = marker.split("delta:", 1)[1].split()[0]
    assert why_coverage_summary(root)["hot"].with_why == 1

    record = resolve_entry(note_id, root=root, source="notes.md").record()
    amend_note(
        note_id,
        "Situation: renaming a public function\nNote: search callers in every package.\nWhy: CI runs only the changed package's tests, so callers elsewhere stay green.\naliases: rename",
        root=root,
        source="notes.md",
        expected_sha256=record["sha256"],
        sess="sess_y",
        author="test",
        reason="sharpen",
        evidence="test",
    )

    assert why_coverage_summary(root)["hot"].with_why == 1
    assert "so callers elsewhere stay green" in (root / "notes.md").read_text(encoding="utf-8")
