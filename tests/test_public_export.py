from pathlib import Path

import pytest

from scripts.export_public import PUBLIC_ENTRIES, export_public


BENCH_ROOT = Path(__file__).resolve().parents[1] / "bench"
SDIST_METADATA = Path(__file__).resolve().parents[1] / "PKG-INFO"


@pytest.mark.skipif(
    not BENCH_ROOT.is_dir() and SDIST_METADATA.is_file(),
    reason="the sdist does not ship bench/ (MANIFEST.in prunes it), so the export source is absent",
)
def test_public_export_contains_only_release_surface(tmp_path: Path):
    export_root = tmp_path / "public"

    copied = export_public(export_root, source_root=Path.cwd())

    assert (export_root / "README.md").exists()
    assert (export_root / "MEMENTO-PATTERN.md").exists()
    assert not (export_root / "IDEA.md").exists()
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
    assert (export_root / "docs/authoring-standards.md").exists()
    assert {path.name for path in (export_root / "docs").iterdir()} == {
        "concepts.md",
        "roadmap.md",
        "save-work.md",
        "essay.md",
        "authoring-standards.md",
        "memento-tattoo-demo.html",
        "memento-memory-hero-v2.png",
    }
    assert {path.name for path in (export_root / "templates").iterdir()} == {
        "AGENTS.md",
        "PROTOCOL.md",
        "memento-stub.md",
    }
    assert (export_root / "src/memento_tattoo/templates/PROTOCOL.md").exists()
    assert (export_root / "src/memento_tattoo/templates/memento-stub.md").exists()
    assert not [path for path in export_root.rglob("memory-layer-judgment-spec.md")]
    assert (export_root / "scripts/export_public.py").exists()
    assert (export_root / "src/memento_tattoo/agent.py").exists()
    assert (export_root / "src/memento_tattoo/new_id.py").exists()
    assert (export_root / "src/memento_tattoo/session_store.py").exists()
    assert (export_root / "src/memento_tattoo/session_archive.py").exists()
    assert (export_root / "src/memento_tattoo/registry.py").exists()
    assert (export_root / "src/memento_tattoo/rebuild.py").exists()
    assert (export_root / "src/memento_tattoo/save_commit.py").exists()
    assert (export_root / "src/memento_tattoo/tattoo_audit.py").exists()
    assert (export_root / "src/memento_tattoo/tattoo_firing.py").exists()
    assert (export_root / "tests/test_agent.py").exists()
    assert (export_root / "tests/test_new_id.py").exists()
    assert (export_root / "tests/test_session_store.py").exists()
    assert (export_root / "tests/test_registry.py").exists()
    assert (export_root / "tests/test_rebuild.py").exists()
    assert (export_root / "tests/test_save_commit.py").exists()
    assert (export_root / "tests/test_concurrent_saves.py").exists()
    assert (export_root / "tests/test_tattoo_firing.py").exists()
    assert (export_root / "SECURITY.md").exists()
    assert (export_root / "bench/w9b/RESULTS.md").exists()
    assert (export_root / "bench/w9b/results/2026-09-28/results.json").exists()
    assert not (export_root / "evidence").exists()
    assert "memory.md" not in copied
    assert not (export_root / "memory.md").exists()
    assert not (export_root / "memento-tattoo-README-draft.md").exists()
    assert not (export_root / "plans").exists()
    assert not (export_root / "research").exists()
    assert not (export_root / "specs").exists()


def test_public_export_contract_uses_the_canonical_pattern_filename():
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    assert "MEMENTO-PATTERN.md" in PUBLIC_ENTRIES
    assert "IDEA.md" not in PUBLIC_ENTRIES
    assert "include MEMENTO-PATTERN.md" in manifest
    assert "exclude IDEA.md" in manifest


def test_packaging_declares_installed_contract_and_template_locations():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '[tool.setuptools.data-files]' in pyproject
    assert '"share/memento-tattoo" = ["MEMENTO-PATTERN.md"]' in pyproject
    assert '"share/memento-tattoo/templates" = ["templates/AGENTS.md", "templates/PROTOCOL.md", "templates/memento-stub.md"]' in pyproject
    assert '[tool.setuptools.package-data]' in pyproject
    assert 'memento_tattoo = ["templates/*.md"]' in pyproject
    assert 'dependencies = []' in pyproject
    assert 'version = "0.5.1"' in pyproject


def test_internal_planning_spec_is_outside_the_public_tree_without_special_excludes():
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")
    exporter = Path("scripts/export_public.py").read_text(encoding="utf-8")

    assert not Path("docs/memory-layer-judgment-spec.md").exists()
    assert "memory-layer-judgment-spec" not in manifest
    assert "memory-layer-judgment-spec" not in exporter
    assert "prune plans" in manifest
    assert "recursive-include src/memento_tattoo/templates *.md" in manifest


def test_packaged_templates_are_byte_identical_to_the_readable_templates():
    for name in ("PROTOCOL.md", "memento-stub.md"):
        readable = Path("templates", name).read_bytes()
        packaged = Path("src/memento_tattoo/templates", name).read_bytes()
        assert packaged == readable, f"copy templates/{name} to src/memento_tattoo/templates/{name}"
