from pathlib import Path

from scripts.export_public import export_public


def test_public_export_contains_only_release_surface(tmp_path: Path):
    export_root = tmp_path / "public"

    copied = export_public(export_root, source_root=Path.cwd())

    assert (export_root / "README.md").exists()
    assert (export_root / "IDEA.md").exists()
    assert (export_root / "pyproject.toml").exists()
    assert (export_root / "MANIFEST.in").exists()
    assert (export_root / ".github/workflows/ci.yml").exists()
    assert (export_root / "examples/basic/README.md").exists()
    assert (export_root / "examples/basic/memento/notes.md").exists()
    assert {path.name for path in (export_root / "examples/basic/memento").iterdir()} == {
        "notes.md",
        "retention_log.jsonl",
        "tattoos.md",
    }
    assert (export_root / "examples/basic/project/memory.md").exists()
    gitignore = (export_root / ".gitignore").read_text(encoding="utf-8")
    assert "/memory.md" in gitignore
    assert "/memento-tattoo-README-draft.md" in gitignore
    assert "/plans/" in gitignore
    assert "/research/" in gitignore
    assert "/specs/" in gitignore
    assert (export_root / "docs/concepts.md").exists()
    assert {path.name for path in (export_root / "docs").iterdir()} == {
        "concepts.md",
        "essay.md",
    }
    assert {path.name for path in (export_root / "templates").iterdir()} == {
        "AGENTS.md",
    }
    assert (export_root / "scripts/export_public.py").exists()
    assert (export_root / "src/memento_tattoo/agent.py").exists()
    assert (export_root / "src/memento_tattoo/new_id.py").exists()
    assert (export_root / "src/memento_tattoo/session_store.py").exists()
    assert (export_root / "src/memento_tattoo/registry.py").exists()
    assert (export_root / "src/memento_tattoo/rebuild.py").exists()
    assert (export_root / "src/memento_tattoo/save_commit.py").exists()
    assert (export_root / "tests/test_agent.py").exists()
    assert (export_root / "tests/test_new_id.py").exists()
    assert (export_root / "tests/test_session_store.py").exists()
    assert (export_root / "tests/test_registry.py").exists()
    assert (export_root / "tests/test_rebuild.py").exists()
    assert (export_root / "tests/test_save_commit.py").exists()
    assert (export_root / "tests/test_concurrent_saves.py").exists()
    assert "memory.md" not in copied
    assert not (export_root / "memory.md").exists()
    assert not (export_root / "memento-tattoo-README-draft.md").exists()
    assert not (export_root / "plans").exists()
    assert not (export_root / "research").exists()
    assert not (export_root / "specs").exists()
