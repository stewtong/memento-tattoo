from pathlib import Path

from memento_tattoo.doctor import run_doctor
from memento_tattoo.garden import build_digest
from memento_tattoo.recall import rank_memento_notes


def test_basic_example_root_is_valid():
    root = Path("examples/basic/memento")
    project = Path("examples/basic/project")

    ok, output = run_doctor(root)
    project_ok, project_output = run_doctor(root, projects=[project])
    ranked = rank_memento_notes("claiming complete verification", root=root)
    project_ranked = rank_memento_notes("package installability built artifact", root=root, projects=[project])
    digest = build_digest(root=root, today="2026-06-17")

    assert ok is True, output
    assert project_ok is True, project_output
    assert ranked[0].note.note_id == "sess_demo.note.11111111"
    assert project_ranked[0].source_name == "project/memory.md"
    assert "Memento gardening digest" in digest


def test_basic_example_has_adjacent_project_memory():
    project_memory = Path("examples/basic/project/memory.md")

    text = project_memory.read_text(encoding="utf-8")
    assert "# Project Memory" in text
    assert "## Key Decisions" in text
    assert "## State" in text
