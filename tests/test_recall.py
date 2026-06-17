from pathlib import Path

from memento_tattoo.recall import load_memento_notes, rank_memento_notes


def test_load_notes_from_delta_blocks(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_one.note.11111111 -->\n"
        "Situation: writing external docs\n"
        "Note: scan for private names before publishing\n"
        "aliases: publish, public, sanitize\n"
        "review_after: 2026-09-01\n",
        encoding="utf-8",
    )

    notes = load_memento_notes(tmp_path)

    assert len(notes) == 1
    assert notes[0].note_id == "sess_one.note.11111111"
    assert notes[0].situation == "writing external docs"
    assert notes[0].review_after == "2026-09-01"


def test_rank_notes_prefers_alias_match(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_one.note.11111111 -->\n"
        "Situation: writing external docs\n"
        "Note: scan for private names before publishing\n"
        "aliases: publish, public, sanitize\n\n"
        "<!-- delta:sess_two.note.22222222 -->\n"
        "Situation: debugging tests\n"
        "Note: reproduce public failures before fixing\n",
        encoding="utf-8",
    )

    ranked = rank_memento_notes("sanitize public release", root=tmp_path, limit=2)

    assert ranked[0].note.note_id == "sess_one.note.11111111"
    assert ranked[0].score > ranked[1].score


def test_rank_notes_omits_zero_score_results(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_one.note.11111111 -->\n"
        "Situation: writing external docs\n"
        "Note: scan for private names before publishing\n"
        "aliases: publish, public, sanitize\n\n"
        "<!-- delta:sess_two.note.22222222 -->\n"
        "Situation: debugging tests\n"
        "Note: reproduce before fixing\n",
        encoding="utf-8",
    )

    ranked = rank_memento_notes("sanitize public release", root=tmp_path, limit=8)

    assert [item.note.note_id for item in ranked] == ["sess_one.note.11111111"]


def test_rank_includes_project_memory_and_tattoos(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_note.note.11111111 -->\n"
        "Situation: local note\n"
        "Note: remember local lesson\n",
        encoding="utf-8",
    )
    (tmp_path / "project.md").write_text(
        "# Project memory\n\n"
        "## State\n\n"
        "- Situation: release readiness\n"
        "- Note: verify installability before publishing\n",
        encoding="utf-8",
    )
    (tmp_path / "tattoos.md").write_text(
        "# Tattoos\n\n"
        "<!-- delta:sess_tattoo.tattoo.22222222 -->\n"
        "- Before trusting aggregate metrics, check the dominant category.\n",
        encoding="utf-8",
    )

    install_ranked = rank_memento_notes("installability publishing", root=tmp_path, limit=3)
    metric_ranked = rank_memento_notes("aggregate metrics dominant category", root=tmp_path, limit=3)

    assert install_ranked[0].source_name == "project.md"
    assert metric_ranked[0].source_name == "tattoos.md"


def test_rank_includes_adjacent_project_memory(tmp_path: Path):
    root = tmp_path / ".memento"
    root.mkdir()
    (root / "notes.md").write_text("", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text(
        "# Project Memory\n\n"
        "## Key Decisions\n\n"
        "- Use a clean release tree for public publishing.\n\n"
        "## State\n\n"
        "- Situation: public release readiness\n"
        "- Note: publish from the sanitized release tree after tests pass.\n",
        encoding="utf-8",
    )

    ranked = rank_memento_notes("sanitized release", root=root, projects=[project], limit=3)

    assert ranked[0].source_name.endswith("memory.md")
    assert ranked[0].note.note_id == "project:memory.md:1"
