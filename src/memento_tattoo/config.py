from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


@dataclass(frozen=True)
class MementoPaths:
    root: Path
    notes: Path
    project: Path
    tattoos: Path
    retention_log: Path
    lock: Path
    sessions: Path
    reserved_ids: Path
    queue: Path
    registry: Path


PathLike = Union[str, Path]


def resolve_root(root: Optional[PathLike] = None) -> Path:
    if root is None:
        env_root = os.environ.get("MEMENTO_TATTOO_ROOT")
        root = env_root if env_root else Path.cwd() / "memento"
    return Path(root).expanduser().resolve()


def resolve_project(project: PathLike) -> Path:
    return Path(project).expanduser().resolve()


def project_memory_path(project: PathLike) -> Path:
    return resolve_project(project) / "memory.md"


def paths_for(root: Optional[PathLike] = None) -> MementoPaths:
    base = resolve_root(root)
    return MementoPaths(
        root=base,
        notes=base / "notes.md",
        project=base / "project.md",
        tattoos=base / "tattoos.md",
        retention_log=base / "retention_log.jsonl",
        lock=base / ".memento.lock",
        sessions=base / "sessions",
        reserved_ids=base / ".reserved_ids",
        queue=base / "_queue",
        registry=base / "registry.md",
    )
