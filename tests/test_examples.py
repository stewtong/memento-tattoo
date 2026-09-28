from pathlib import Path

from memento_tattoo.doctor import run_doctor
from memento_tattoo.garden import build_digest
from memento_tattoo.recall import rank_memento_notes


def test_basic_example_root_is_valid():
    root = Path("examples/basic/memento")
    project = Path("examples/basic/project")

    ok, output = run_doctor(root)
    project_ok, project_output = run_doctor(root, projects=[project])
    ranked = rank_memento_notes("changing a package public API callers", root=root)
    project_ranked = rank_memento_notes("billing rename format_money", root=root, projects=[project])
    digest = build_digest(root=root, today="2026-06-17")

    assert ok is True, output
    assert project_ok is True, project_output
    assert ranked[0].note.note_id == "sess_demo.note.11111111"
    assert project_ranked[0].source_name == "project/memory.md"
    assert "Memento gardening digest" in digest
    assert ranked[1].note.note_id == "sess_demo.tattoo.33333333"
    assert "why-coverage: hot 3/3 with Why; archive 0/0 with Why" in output
    assert "tattoo-reasons: 1/1 with a reason clause" in output


def test_basic_example_has_adjacent_project_memory():
    project_memory = Path("examples/basic/project/memory.md")

    text = project_memory.read_text(encoding="utf-8")
    assert "# Project Memory" in text
    assert "## Key Decisions" in text
    assert "## Current state" in text
