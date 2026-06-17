from pathlib import Path

from memento_tattoo.config import paths_for, project_memory_path, resolve_project, resolve_root


def test_resolve_root_expands_and_resolves(tmp_path: Path):
    root = tmp_path / "mem"
    root.mkdir()

    assert resolve_root(root) == root.resolve()


def test_paths_for_uses_single_memento_root(tmp_path: Path):
    paths = paths_for(tmp_path)

    assert paths.root == tmp_path.resolve()
    assert paths.notes == tmp_path / "notes.md"
    assert paths.project == tmp_path / "project.md"
    assert paths.tattoos == tmp_path / "tattoos.md"
    assert paths.retention_log == tmp_path / "retention_log.jsonl"
    assert paths.lock == tmp_path / ".memento.lock"


def test_resolve_project_expands_to_absolute_path(tmp_path: Path):
    project = tmp_path / "project"
    resolved = resolve_project(project)

    assert resolved == project.resolve()


def test_project_memory_path_is_adjacent_to_project_root(tmp_path: Path):
    project = tmp_path / "project"

    assert project_memory_path(project) == project.resolve() / "memory.md"
