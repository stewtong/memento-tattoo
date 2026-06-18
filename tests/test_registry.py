from pathlib import Path

from memento_tattoo.registry import drain, registry_queue, slugify


def test_slugify_normalizes_human_names():
    assert slugify("Agent Skills") == "agent-skills"
    assert slugify("  Memento OSS!! ") == "memento-oss"
    assert slugify("") == "unnamed"


def test_registry_queue_uses_unique_filenames_for_same_session_slug(tmp_path: Path):
    first = registry_queue("sess_abcd", "update", "Agent Skills", "- Agent Skills - agent_skills/ - active", tmp_path, agent="codex")
    second = registry_queue("sess_abcd", "update", "Agent Skills", "- Agent Skills - agent_skills/ - active", tmp_path, agent="codex")

    assert first != second
    assert first.exists()
    assert second.exists()
    assert first.name.endswith(".registry.md")
    assert ".sess_abcd.agent-skills." in first.name


def test_drain_applies_add_update_and_archive(tmp_path: Path):
    registry_queue("sess_a111", "add", "memento-oss", "- Memento OSS - memento-oss/ - active", tmp_path, agent="codex")
    ok = drain(tmp_path)
    assert not ok.skipped

    registry_queue("sess_a112", "update", "memento-oss", "- Memento OSS - memento-oss/ - maintained", tmp_path, agent="claude")
    registry_queue("sess_a113", "archive", "memento-oss", "- Memento OSS - memento-oss/ - active", tmp_path, agent="codex")
    result = drain(tmp_path)

    text = (tmp_path / "registry.md").read_text(encoding="utf-8")
    assert result.applied == 1
    assert result.conflicts == 1
    assert "slug=memento-oss" in text
    assert "status=archived" in text
    assert "- Memento OSS - memento-oss/ - archived" in text


def test_same_slug_collision_preserves_loser(tmp_path: Path):
    registry_queue("sess_a111", "update", "memento-oss", "- Memento OSS - old/ - active", tmp_path, agent="codex", ts="2026-06-17T00:00:00Z")
    registry_queue("sess_a112", "update", "memento-oss", "- Memento OSS - new/ - active", tmp_path, agent="claude", ts="2026-06-17T00:00:01Z")

    result = drain(tmp_path)

    text = (tmp_path / "registry.md").read_text(encoding="utf-8")
    conflicts = list((tmp_path / "_queue" / "conflicts").glob("*.registry.md"))
    assert result.conflicts == 1
    assert "registry-conflict" in text
    assert "new/" in text
    assert conflicts
    assert "old/" in conflicts[0].read_text(encoding="utf-8")


def test_double_drain_is_idempotent(tmp_path: Path):
    registry_queue("sess_a111", "add", "memento-oss", "- Memento OSS - memento-oss/ - active", tmp_path, agent="codex")

    first = drain(tmp_path)
    second = drain(tmp_path)

    assert first.applied == 1
    assert second.applied == 0
    assert not list((tmp_path / "_queue").glob("*.registry.md"))
