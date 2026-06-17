from pathlib import Path

from scripts.export_public import export_public


def test_public_export_contains_only_release_surface(tmp_path: Path):
    export_root = tmp_path / "public"

    copied = export_public(export_root, source_root=Path.cwd())

    assert (export_root / "README.md").exists()
    assert (export_root / "pyproject.toml").exists()
    assert (export_root / "MANIFEST.in").exists()
    assert (export_root / ".github/workflows/ci.yml").exists()
    assert (export_root / "examples/basic/memento/notes.md").exists()
    assert {path.name for path in (export_root / "examples/basic/memento").iterdir()} == {
        "notes.md",
        "retention_log.jsonl",
        "tattoos.md",
    }
    assert (export_root / "examples/basic/project/memory.md").exists()
    assert "/memory.md" in (export_root / ".gitignore").read_text(encoding="utf-8")
    assert (export_root / "docs/concepts.md").exists()
    assert {path.name for path in (export_root / "docs").iterdir()} == {
        "concepts.md",
        "essay.md",
    }
    assert (export_root / "scripts/export_public.py").exists()
    assert "memory.md" not in copied
    assert not (export_root / "memory.md").exists()
    assert not (export_root / "plans").exists()
    assert not (export_root / "research").exists()
    assert not (export_root / "specs").exists()
