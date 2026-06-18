from pathlib import Path

from memento_tattoo.project_memory import ensure_project_memory
from memento_tattoo.write_through import project_edit


def test_ensure_project_memory_creates_required_sections(tmp_path: Path):
    project = tmp_path / "project"

    path = ensure_project_memory(project)

    assert path == project.resolve() / "memory.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Project Memory\n")
    assert "## Key Decisions\n" in text
    assert "## State\n" in text


def test_project_edit_replaces_named_section(tmp_path: Path):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    ensure_project_memory(project)

    applied, marker = project_edit(
        "- Shipped package scaffold.\n- Next: add examples.",
        sess="sess_abcd",
        root=root,
        project=project,
        section="## State",
    )

    assert applied is True
    text = (project / "memory.md").read_text(encoding="utf-8")
    assert marker in text
    assert "## State\n\n" in text
    assert "- Shipped package scaffold." in text
    assert "- Next: add examples." in text


def test_project_edit_is_idempotent_for_same_session_and_body(tmp_path: Path):
    root = tmp_path / ".memento"
    project = tmp_path / "project"

    first, marker = project_edit("state body", sess="sess_abcd", root=root, project=project, section="## State")
    second, second_marker = project_edit("state body", sess="sess_abcd", root=root, project=project, section="## State")

    text = (project / "memory.md").read_text(encoding="utf-8")
    assert first is True
    assert second is False
    assert marker == second_marker
    assert text.count(marker) == 1


def test_project_edit_preserves_changed_section_when_flow_start_is_stale(tmp_path: Path):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    memory = ensure_project_memory(project)
    memory.write_text(
        "# Project Memory\n\n"
        "## Key Decisions\n\n"
        "## State\n\n"
        "<!-- delta:sess_other.project.11111111 -->\n"
        "- Other agent state.\n",
        encoding="utf-8",
    )

    applied, marker = project_edit(
        "- Current agent state.",
        sess="sess_abcd",
        root=root,
        project=project,
        section="## State",
        flow_start="1970-01-01T00:00:00Z",
    )

    text = memory.read_text(encoding="utf-8")
    assert applied is True
    assert marker in text
    assert "concurrent-edit reconcile" in text
    assert "- Other agent state." in text
    assert "- Current agent state." in text


def test_project_edit_replaces_old_marker_before_flow_start(tmp_path: Path):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    memory = ensure_project_memory(project)
    memory.write_text(
        "# Project Memory\n\n"
        "## Key Decisions\n\n"
        "## State\n\n"
        "<!-- delta:sess_other.project.11111111 agent=codex ts=2026-06-17T00:00:00Z -->\n"
        "- Old state.\n",
        encoding="utf-8",
    )

    project_edit(
        "- Current state.",
        sess="sess_abcd",
        root=root,
        project=project,
        section="## State",
        flow_start="2026-06-17T01:00:00Z",
    )

    text = memory.read_text(encoding="utf-8")
    assert "concurrent-edit reconcile" not in text
    assert "- Old state." not in text
    assert "- Current state." in text


def test_project_edit_preserves_marker_after_flow_start(tmp_path: Path):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    memory = ensure_project_memory(project)
    memory.write_text(
        "# Project Memory\n\n"
        "## Key Decisions\n\n"
        "## State\n\n"
        "<!-- delta:sess_other.project.11111111 agent=codex ts=2026-06-17T02:00:00Z -->\n"
        "- Concurrent state.\n",
        encoding="utf-8",
    )

    project_edit(
        "- Current state.",
        sess="sess_abcd",
        root=root,
        project=project,
        section="## State",
        flow_start="2026-06-17T01:00:00Z",
    )

    text = memory.read_text(encoding="utf-8")
    assert "concurrent-edit reconcile" in text
    assert "- Concurrent state." in text
    assert "- Current state." in text
