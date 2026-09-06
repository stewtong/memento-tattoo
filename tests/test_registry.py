from pathlib import Path

from memento_tattoo.registry import drain, registry_queue, slugify


def test_slugify_normalizes_human_names():
    assert slugify("Agent Skills") == "agent-skills"
    assert slugify("  Memento OSS!! ") == "memento-oss"
    assert slugify("") == "unnamed"


def test_registry_queue_reuses_identical_operation_receipt(tmp_path: Path):
    first = registry_queue("sess_abcd", "update", "Agent Skills", "- Agent Skills - agent_skills/ - active", tmp_path, agent="codex")
    second = registry_queue("sess_abcd", "update", "Agent Skills", "- Agent Skills - agent_skills/ - active", tmp_path, agent="codex")

    assert first == second
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


def test_prune_applied_keeps_newest_and_archives_older(tmp_path: Path):
    import os
    from memento_tattoo.registry import prune_applied
    applied = tmp_path / "applied"
    applied.mkdir()
    for i in range(5):
        p = applied / f"sess_{i}.proj.registry.md"
        p.write_text(f"delta {i}", encoding="utf-8")
        os.utime(p, (1000 + i, 1000 + i))
    removed = prune_applied(applied, keep=3)
    remaining = sorted(q.name for q in applied.glob("*.registry.md"))
    assert removed == 2
    assert len(list((applied / "archive").glob("*.registry.md"))) == 2
    assert remaining == ["sess_2.proj.registry.md", "sess_3.proj.registry.md", "sess_4.proj.registry.md"]


def test_prune_applied_noop_when_under_limit(tmp_path: Path):
    from memento_tattoo.registry import prune_applied
    applied = tmp_path / "applied"
    applied.mkdir()
    (applied / "sess_a.proj.registry.md").write_text("x", encoding="utf-8")
    assert prune_applied(applied, keep=100) == 0


def test_prune_applied_missing_dir_is_safe(tmp_path: Path):
    from memento_tattoo.registry import prune_applied
    assert prune_applied(tmp_path / "nope", keep=10) == 0
