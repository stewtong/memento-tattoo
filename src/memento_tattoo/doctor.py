from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import paths_for, project_memory_path
from .retention import read_retention_events


def run_doctor(root: Path, projects: Optional[list[Path]] = None) -> tuple[bool, str]:
    paths = paths_for(root)
    checks: list[tuple[str, str, str]] = []
    project_list = projects or []
    has_project_scope = bool(project_list)

    for label, path in (
        ("notes", paths.notes),
        ("tattoos", paths.tattoos),
    ):
        if path.exists():
            checks.append(("pass", label, f"{path.name} present"))
        else:
            status = "warn" if has_project_scope else "fail"
            checks.append((status, label, f"{path.name} missing"))

    if paths.project.exists():
        checks.append(("pass", "project", f"{paths.project.name} present"))
    else:
        checks.append(("warn", "project", f"{paths.project.name} missing; use adjacent project memory.md for new roots"))

    for project in project_list:
        path = project_memory_path(project)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if "## Key Decisions" in text and "## State" in text:
                checks.append(("pass", "project-memory", f"{path.name} present for {Path(project).name}"))
            else:
                checks.append(("fail", "project-memory", f"{path.name} missing required sections for {Path(project).name}"))
        else:
            checks.append(("fail", "project-memory", f"{path.name} missing for {Path(project).name}"))

    if not paths.retention_log.exists():
        checks.append(("warn", "retention", "retention_log.jsonl missing"))
    else:
        try:
            events = read_retention_events(root=paths.root)
        except Exception as exc:
            checks.append(("fail", "retention", f"retention_log.jsonl unreadable: {exc}"))
        else:
            checks.append(("pass", "retention", f"retention events: {len(events)}"))

    ok = all(status != "fail" for status, _, _ in checks)
    lines = ["MEMENTO_TATTOO_DOCTOR"]
    lines.extend(f"{status.upper():5} {name}: {detail}" for status, name, detail in checks)
    return ok, "\n".join(lines)
