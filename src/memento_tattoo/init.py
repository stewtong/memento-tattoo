"""Create a memory root, install the agent protocol, and emit instruction-file adapters.

`init` never overwrites an existing file. Each target is created when absent and
reported as skipped when present, so repeated runs are safe.

The protocol and the always-on stub are package data under
``memento_tattoo/templates/``. The human-readable copies in the repository's
``templates/`` directory must stay byte-identical; a test enforces that.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Optional

ADAPTERS = ("generic", "skill", "claude-md-import")
SKILL_NAME = "memento-tattoo"
DEFAULT_SKILL_PARENT = Path(".agents") / "skills"
CLAUDE_IMPORT_LINE = "@AGENTS.md"

PROJECT_MEMORY_SKELETON = "# Project Memory\n\n## Key Decisions\n\n## Current state\n"
TATTOOS_SKELETON = "# Tattoos\n"

SKILL_DESCRIPTION = (
    "Repo memory of corrections, lessons and approved rules kept as Markdown under memento/. "
    "Use when the user corrects you, when you recognize the situation of a past lesson, "
    'or when the user says "save work". It points to memento/PROTOCOL.md, which holds the procedure.'
)


def template_text(name: str) -> str:
    """Return a packaged template by file name."""
    return resources.files("memento_tattoo").joinpath("templates", name).read_text(encoding="utf-8")


def protocol_text() -> str:
    return template_text("PROTOCOL.md")


def stub_text() -> str:
    return template_text("memento-stub.md")


@dataclass
class InitResult:
    root: Path
    project: Path
    lines: list[str] = field(default_factory=list)
    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)

    def record(self, path: Path, created: bool, note: str = "") -> None:
        (self.created if created else self.skipped).append(path)
        verb = "created" if created else "skipped (exists)"
        self.lines.append(f"{verb} {path}{note}")


def _write_new(path: Path, text: str, result: InitResult) -> None:
    """Create ``path`` with ``text`` unless something already exists there."""
    if path.exists() or path.is_symlink():
        result.record(path, created=False)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError:
        result.record(path, created=False)
        return
    result.record(path, created=True)


def _default_project(root: Path) -> Path:
    """The repository the memory root belongs to.

    When init runs from a directory that contains the root (the usual case: the
    repository root), that directory is the project, so a nested root such as
    ``tools/mem`` is still addressed from the repository root. Otherwise the
    root's parent is used.
    """
    cwd = Path.cwd().resolve()
    if root != cwd and cwd in root.parents:
        return cwd
    return root.parent


def _root_prefix(root: Path, project: Path) -> str:
    """Return the memory root as written in instructions, relative to the project when possible."""
    try:
        relative = os.path.relpath(root, project)
    except ValueError:
        return root.as_posix()
    if relative.startswith(".."):
        return root.as_posix()
    return Path(relative).as_posix()


def localize(text: str, root: Path, project: Path) -> str:
    """Point instruction text at the actual memory root when it is not ``memento/``."""
    prefix = _root_prefix(root, project)
    if prefix == "memento":
        return text
    return text.replace("memento/", prefix.rstrip("/") + "/")


def skill_markdown(root: Path, project: Path) -> str:
    prefix = _root_prefix(root, project)
    protocol_path = f"{prefix.rstrip('/')}/PROTOCOL.md"
    description = SKILL_DESCRIPTION.replace("memento/", prefix.rstrip("/") + "/")
    return (
        "---\n"
        f"name: {SKILL_NAME}\n"
        f"description: {json.dumps(description)}\n"
        "---\n"
        "\n"
        f"# {SKILL_NAME}\n"
        "\n"
        f"Open `{protocol_path}` from the repository root and follow the section that matches "
        "what just happened: a correction, a situation you recognize from a past lesson, or a "
        "request to save work.\n"
        "\n"
        f"`{protocol_path}` is the only copy of the procedure. This skill points to it, so the "
        "two cannot disagree.\n"
    )


def run_init(
    root: Path,
    *,
    project: Optional[Path] = None,
    adapter: str = "generic",
    skill_dir: Optional[Path] = None,
    write_claude_md: bool = False,
) -> InitResult:
    if adapter not in ADAPTERS:
        raise ValueError(f"unknown adapter {adapter!r}; choose from {', '.join(ADAPTERS)}")
    root = Path(root).expanduser().resolve()
    project = Path(project).expanduser().resolve() if project is not None else _default_project(root)
    result = InitResult(root=root, project=project)
    result.lines.append("MEMENTO_TATTOO_INIT")
    result.lines.append(f"root: {root}")
    result.lines.append(f"project: {project}")

    _write_new(root / "notes.md", "", result)
    _write_new(root / "tattoos.md", TATTOOS_SKELETON, result)
    _write_new(root / "retention_log.jsonl", "", result)
    _write_new(root / "PROTOCOL.md", protocol_text(), result)
    _write_new(project / "memory.md", PROJECT_MEMORY_SKELETON, result)

    if adapter == "skill":
        parent = Path(skill_dir).expanduser() if skill_dir is not None else project / DEFAULT_SKILL_PARENT
        if not parent.is_absolute():
            parent = Path.cwd() / parent
        _write_new(parent.resolve() / SKILL_NAME / "SKILL.md", skill_markdown(root, project), result)

    if adapter == "claude-md-import":
        claude_md = project / "CLAUDE.md"
        if write_claude_md:
            _write_new(claude_md, CLAUDE_IMPORT_LINE + "\n", result)
            if claude_md in result.skipped:
                present = CLAUDE_IMPORT_LINE in claude_md.read_text(encoding="utf-8").splitlines()
                result.lines.append(
                    "CLAUDE.md already imports AGENTS.md" if present else "CLAUDE.md exists; add this line to it:"
                )
                if not present:
                    result.lines.append(CLAUDE_IMPORT_LINE)
        else:
            result.lines.append("")
            result.lines.append("Add this line to CLAUDE.md so it imports AGENTS.md:")
            result.lines.append("")
            result.lines.append(CLAUDE_IMPORT_LINE)

    result.lines.append("")
    result.lines.append("Paste this into the instruction file your agent reads (AGENTS.md, CLAUDE.md, or a rules file):")
    result.lines.append("")
    result.lines.append(localize(stub_text(), root, project).rstrip("\n"))
    return result
