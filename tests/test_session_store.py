from pathlib import Path

import pytest

from memento_tattoo.session_store import (
    load_sessions,
    render_session_block,
    session_source_files,
    write_session_block,
)


def test_loads_flat_current_session(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_a111.md").write_text(
        "---\n"
        "[sess_a111 | 2026-06-17 10:00 | codex | docs, tests | medium]\n"
        "Accomplished: A.\n"
        "Started: B.\n"
        "Pending: C.\n"
        "Insights: D.\n"
        "Files: README.md; templates/AGENTS.md\n"
        "---\n",
        encoding="utf-8",
    )

    records = load_sessions(tmp_path)

    assert len(records) == 1
    assert records[0].sess == "sess_a111"
    assert records[0].agent == "codex"
    assert records[0].topics == ["docs", "tests"]
    assert records[0].significance == "medium"
    assert records[0].accomplished == "A."
    assert records[0].files == ["README.md", "templates/AGENTS.md"]


def test_loads_grandfathered_three_part_header(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_old1.md").write_text(
        "---\n"
        "[sess_old1 | 2026-06-01 09:00 | docs, tests]\n"
        "Accomplished: Legacy.\n"
        "---\n",
        encoding="utf-8",
    )

    record = load_sessions(tmp_path)[0]

    assert record.agent == "grandfathered"
    assert record.topics == ["docs", "tests"]
    assert record.significance == "unknown"


def test_session_source_files_include_archive(tmp_path: Path):
    sessions = tmp_path / "sessions"
    archive = sessions / "archive"
    archive.mkdir(parents=True)
    current = sessions / "sess_now.md"
    archived = archive / "sess_old.md"
    current.write_text("", encoding="utf-8")
    archived.write_text("", encoding="utf-8")

    assert session_source_files(tmp_path) == [archived, current]


def test_render_session_block_and_write_idempotently(tmp_path: Path):
    block = render_session_block(
        "sess_abcd",
        date="2026-06-17 18:24",
        agent="Codex CLI",
        topics=["memento-oss", "multi-agent"],
        significance="medium",
        accomplished="Published docs polish.",
        started="none.",
        pending="none.",
        insights="none.",
        files=["README.md", "templates/AGENTS.md"],
    )

    path = write_session_block(tmp_path, block, "sess_abcd")
    again = write_session_block(tmp_path, block, "sess_abcd")

    assert path == again
    assert path == tmp_path / "sessions" / "sess_abcd.md"
    assert "codex-cli" in path.read_text(encoding="utf-8")
    assert "Files: README.md; templates/AGENTS.md" in path.read_text(encoding="utf-8")


def test_write_session_block_refuses_different_existing_content(tmp_path: Path):
    first = render_session_block(
        "sess_abcd",
        date="2026-06-17 18:24",
        agent="codex",
        topics=["docs"],
        significance="medium",
        accomplished="A.",
        started="none.",
        pending="none.",
        insights="none.",
        files=[],
    )
    second = first.replace("Accomplished: A.", "Accomplished: B.")
    write_session_block(tmp_path, first, "sess_abcd")

    with pytest.raises(FileExistsError):
        write_session_block(tmp_path, second, "sess_abcd")
